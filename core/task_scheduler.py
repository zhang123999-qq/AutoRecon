#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 扫描任务调度器
支持优先级队列、重试机制、限流、定时执行、分布式锁
"""

import asyncio
import heapq
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Awaitable, Any
from enum import Enum
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass(order=True)
class ScheduledTask:
    """调度任务"""
    priority: TaskPriority
    scheduled_at: datetime
    task_id: str = field(compare=False)
    coro_factory: Callable[[], Awaitable[Any]] = field(compare=False)
    kwargs: Dict[str, Any] = field(default_factory=dict, compare=False)
    retries: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    timeout: float = field(default=300.0, compare=False)
    tags: List[str] = field(default_factory=list, compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)
    
    def __post_init__(self):
        # 确保 scheduled_at 是 datetime
        if isinstance(self.scheduled_at, (int, float)):
            self.scheduled_at = datetime.fromtimestamp(self.scheduled_at)


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: float = 0.0
    retries: int = 0
    
    @property
    def success(self) -> bool:
        return self.status == TaskStatus.COMPLETED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "retries": self.retries,
        }


class RateLimiter:
    """令牌桶限流器"""
    
    def __init__(self, rate: float, burst: int):
        self.rate = rate  # tokens per second
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """获取令牌，返回等待时间"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            # 计算等待时间
            needed = tokens - self.tokens
            wait_time = needed / self.rate
            self.tokens = 0
            return wait_time
    
    async def __aenter__(self):
        wait = await self.acquire()
        if wait > 0:
            await asyncio.sleep(wait)
        return self
    
    async def __aexit__(self, *args):
        pass


class ConcurrencyLimiter:
    """并发限制器"""
    
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running = 0
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def limit(self):
        await self.semaphore.acquire()
        async with self._lock:
            self.running += 1
        try:
            yield
        finally:
            self.semaphore.release()
            async with self._lock:
                self.running -= 1
    
    def current_running(self) -> int:
        return self.running


class TaskScheduler:
    """任务调度器
    
    功能:
    - 优先级队列调度
    - 定时/延迟执行
    - 自动重试 (指数退避)
    - 并发控制
    - 限流控制
    - 超时管理
    - 任务取消
    - 进度回调
    - 结果持久化
    """
    
    def __init__(
        self,
        max_concurrent: int = 10,
        default_timeout: float = 300.0,
        default_max_retries: int = 3,
        rate_limit: float = 0,  # 0 = 无限制
        rate_burst: int = 0,
    ):
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries
        
        # 队列和状态
        self._queue: List[ScheduledTask] = []
        self._running: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, TaskResult] = {}
        self._cancelled: set = set()
        
        # 并发和限流
        self.concurrency_limiter = ConcurrencyLimiter(max_concurrent)
        self.rate_limiter = RateLimiter(rate_limit, rate_burst) if rate_limit > 0 else None
        
        # 回调
        self._progress_callback: Optional[Callable[[str, TaskStatus, Dict], None]] = None
        self._completion_callback: Optional[Callable[[TaskResult], None]] = None
        
        # 统计
        self.stats = {
            "total_scheduled": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_retries": 0,
        }
        
        # 运行标志
        self._running_flag = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    def set_progress_callback(self, callback: Callable[[str, TaskStatus, Dict], None]):
        """设置进度回调: callback(task_id, status, metadata)"""
        self._progress_callback = callback
    
    def set_completion_callback(self, callback: Callable[[TaskResult], None]):
        """设置完成回调"""
        self._completion_callback = callback
    
    def schedule(
        self,
        coro_factory: Callable[[], Awaitable[Any]],
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: float = 0,
        task_id: str = None,
        max_retries: int = None,
        timeout: float = None,
        tags: List[str] = None,
        **kwargs
    ) -> str:
        """调度任务
        
        Args:
            coro_factory: 返回 awaitable 的工厂函数
            priority: 优先级
            delay: 延迟秒数
            task_id: 任务ID (自动生成)
            max_retries: 最大重试次数
            timeout: 超时秒数
            tags: 标签
            **kwargs: 传递给 coro_factory 的参数
            
        Returns:
            task_id
        """
        task_id = task_id or str(uuid.uuid4())[:8]
        scheduled_at = datetime.now() + timedelta(seconds=delay)
        
        task = ScheduledTask(
            priority=priority,
            scheduled_at=scheduled_at,
            task_id=task_id,
            coro_factory=coro_factory,
            kwargs=kwargs,
            max_retries=max_retries or self.default_max_retries,
            timeout=timeout or self.default_timeout,
            tags=tags or [],
        )
        
        heapq.heappush(self._queue, task)
        self.stats["total_scheduled"] += 1
        
        logger.debug(f"任务已调度: {task_id} (优先级: {priority.name}, 延迟: {delay}s)")
        return task_id
    
    def schedule_at(
        self,
        coro_factory: Callable[[], Awaitable[Any]],
        scheduled_at: datetime,
        priority: TaskPriority = TaskPriority.NORMAL,
        task_id: str = None,
        **kwargs
    ) -> str:
        """在指定时间调度任务"""
        delay = (scheduled_at - datetime.now()).total_seconds()
        return self.schedule(coro_factory, priority, max(0, delay), task_id, **kwargs)
    
    def schedule_recurring(
        self,
        coro_factory: Callable[[], Awaitable[Any]],
        interval: float,
        priority: TaskPriority = TaskPriority.NORMAL,
        task_id: str = None,
        max_runs: int = 0,  # 0 = 无限
        **kwargs
    ) -> str:
        """调度周期性任务"""
        task_id = task_id or str(uuid.uuid4())[:8]
        run_count = 0
        
        async def recurring_wrapper():
            nonlocal run_count
            while max_runs == 0 or run_count < max_runs:
                try:
                    await coro_factory()
                except Exception as e:
                    logger.error(f"周期任务异常 {task_id}: {e}")
                
                run_count += 1
                if max_runs == 0 or run_count < max_runs:
                    await asyncio.sleep(interval)
        
        return self.schedule(recurring_wrapper, priority, task_id=task_id, **kwargs)
    
    async def start(self):
        """启动调度器"""
        if self._running_flag:
            return
        
        self._running_flag = True
        self._scheduler_task = asyncio.create_task(self._run_loop())
        logger.info(f"调度器启动 (最大并发: {self.max_concurrent})")
    
    async def stop(self, wait: bool = True, timeout: float = 30.0):
        """停止调度器"""
        self._running_flag = False
        
        if wait and self._running:
            # 等待运行中任务完成
            done, pending = await asyncio.wait(
                self._running.values(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # 取消未完成的
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("调度器已停止")
    
    async def _run_loop(self):
        """调度器主循环"""
        while self._running_flag:
            try:
                # 启动可运行的任务
                await self._start_ready_tasks()
                
                # 等待下一个调度点
                if self._queue:
                    next_task = self._queue[0]
                    wait_time = (next_task.scheduled_at - datetime.now()).total_seconds()
                    if wait_time > 0:
                        await asyncio.sleep(min(wait_time, 1.0))
                    else:
                        await asyncio.sleep(0.01)  # 立即可运行
                else:
                    await asyncio.sleep(1.0)  # 空闲等待
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度器循环异常: {e}")
                await asyncio.sleep(1.0)
    
    async def _start_ready_tasks(self):
        """启动所有就绪任务"""
        now = datetime.now()
        
        while self._queue and len(self._running) < self.max_concurrent:
            task = self._queue[0]
            
            if task.scheduled_at <= now:
                heapq.heappop(self._queue)
                
                if task.task_id in self._cancelled:
                    self._cancelled.discard(task.task_id)
                    continue
                
                # 创建运行任务
                run_task = asyncio.create_task(self._execute_task(task))
                self._running[task.task_id] = run_task
            else:
                break
    
    async def _execute_task(self, task: ScheduledTask):
        """执行单个任务"""
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.RUNNING,
            started_at=time.time(),
            retries=task.retries,
        )
        self._results[task.task_id] = result
        
        # 进度回调
        if self._progress_callback:
            try:
                self._progress_callback(task.task_id, TaskStatus.RUNNING, {
                    "retries": task.retries,
                    "tags": task.tags,
                })
            except Exception:
                pass
        
        try:
            # 并发控制
            async with self.concurrency_limiter.limit():
                # 限流
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                # 执行带超时
                result.result = await asyncio.wait_for(
                    task.coro_factory(),
                    timeout=task.timeout
                )
                
                result.status = TaskStatus.COMPLETED
                self.stats["total_completed"] += 1
                
        except asyncio.TimeoutError:
            result.status = TaskStatus.FAILED
            result.error = f"任务超时 ({task.timeout}s)"
            await self._handle_retry(task, result)
            
        except asyncio.CancelledError:
            result.status = TaskStatus.CANCELLED
            result.error = "任务被取消"
            self.stats["total_cancelled"] += 1
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            await self._handle_retry(task, result)
            
        finally:
            result.completed_at = time.time()
            result.duration = result.completed_at - result.started_at
            self._results[task.task_id] = result
            
            # 从运行中移除
            self._running.pop(task.task_id, None)
            
            # 完成回调
            if self._completion_callback:
                try:
                    self._completion_callback(result)
                except Exception:
                    pass
            
            if self._progress_callback:
                try:
                    self._progress_callback(task.task_id, result.status, {
                        "duration": result.duration,
                        "error": result.error,
                    })
                except Exception:
                    pass
    
    async def _handle_retry(self, task: ScheduledTask, result: TaskResult):
        """处理重试"""
        if task.retries < task.max_retries:
            task.retries += 1
            result.retries = task.retries
            result.status = TaskStatus.RETRYING
            self.stats["total_retries"] += 1
            
            # 指数退避
            delay = min(2 ** task.retries, 60)  # 最大 60 秒
            task.scheduled_at = datetime.now() + timedelta(seconds=delay)
            heapq.heappush(self._queue, task)
            
            logger.warning(f"任务重试 {task.task_id}: 第 {task.retries} 次, 延迟 {delay}s, 错误: {result.error}")
        else:
            self.stats["total_failed"] += 1
            logger.error(f"任务失败 {task.task_id}: 重试耗尽, 错误: {result.error}")
    
    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        # 检查队列中
        for i, task in enumerate(self._queue):
            if task.task_id == task_id:
                self._queue.pop(i)
                heapq.heapify(self._queue)
                logger.info(f"任务已从队列取消: {task_id}")
                return True
        
        # 检查运行中
        if task_id in self._running:
            self._running[task_id].cancel()
            self._cancelled.add(task_id)
            logger.info(f"任务已发送取消信号: {task_id}")
            return True
        
        return False
    
    def cancel_by_tag(self, tag: str) -> int:
        """按标签取消任务"""
        count = 0
        
        # 队列中
        self._queue = [t for t in self._queue if tag not in t.tags or (count := count + 1) == 0]
        heapq.heapify(self._queue)
        
        # 运行中
        for tid, run_task in list(self._running.items()):
            if tag in self._results.get(tid, TaskResult(tid, TaskStatus.PENDING)).metadata.get("tags", []):
                run_task.cancel()
                self._cancelled.add(tid)
                count += 1
        
        return count
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        return self._results.get(task_id)
    
    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        result = self._results.get(task_id)
        if result:
            return result.status
        
        # 检查队列
        for task in self._queue:
            if task.task_id == task_id:
                return TaskStatus.SCHEDULED
        
        # 检查运行中
        if task_id in self._running:
            return TaskStatus.RUNNING
        
        return None
    
    def wait_for(self, task_id: str, timeout: float = None) -> TaskResult:
        """等待任务完成 (同步版本，需在事件循环外调用)"""
        async def _wait():
            while True:
                result = self.get_result(task_id)
                if result and result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    return result
                await asyncio.sleep(0.1)
        
        return asyncio.run(asyncio.wait_for(_wait(), timeout=timeout))
    
    async def wait_for_async(self, task_id: str, timeout: float = None) -> TaskResult:
        """等待任务完成 (异步版本)"""
        while True:
            result = self.get_result(task_id)
            if result and result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return result
            await asyncio.sleep(0.1)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        pending_by_priority = defaultdict(int)
        for task in self._queue:
            pending_by_priority[task.priority.name] += 1
        
        return {
            "pending": len(self._queue),
            "running": len(self._running),
            "completed": len([r for r in self._results.values() if r.status == TaskStatus.COMPLETED]),
            "failed": len([r for r in self._results.values() if r.status == TaskStatus.FAILED]),
            "pending_by_priority": dict(pending_by_priority),
            "stats": self.stats.copy(),
        }
    
    def get_all_results(self) -> Dict[str, TaskResult]:
        """获取所有结果"""
        return self._results.copy()
    
    def clear_completed(self, max_age: float = 3600):
        """清理旧结果"""
        now = time.time()
        to_remove = []
        for tid, result in self._results.items():
            if result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if result.completed_at and (now - result.completed_at) > max_age:
                    to_remove.append(tid)
        
        for tid in to_remove:
            del self._results[tid]
        
        return len(to_remove)


class DistributedLock:
    """分布式锁 (基于 Redis)"""
    
    def __init__(self, redis_client, key: str, ttl: int = 30):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.ttl = ttl
        self._locked = False
        self._lock_value = str(uuid.uuid4())
    
    async def acquire(self, blocking: bool = True, timeout: float = 10) -> bool:
        """获取锁"""
        start = time.time()
        
        while True:
            # SET NX EX
            acquired = await self.redis.set(
                self.key, self._lock_value, nx=True, ex=self.ttl
            )
            
            if acquired:
                self._locked = True
                return True
            
            if not blocking:
                return False
            
            if time.time() - start > timeout:
                return False
            
            await asyncio.sleep(0.1)
    
    async def release(self) -> bool:
        """释放锁 (使用 Lua 脚本保证原子性)"""
        if not self._locked:
            return False
        
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            result = await self.redis.eval(lua_script, 1, self.key, self._lock_value)
            self._locked = False
            return result == 1
        except Exception:
            self._locked = False
            return False
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, *args):
        await self.release()


class TaskQueue:
    """持久化任务队列 (可选集成)"""
    
    def __init__(self, storage_backend):
        self.storage = storage_backend  # 可实现为 Redis, SQLite, 文件等
    
    async def enqueue(self, task: ScheduledTask) -> bool:
        """入队"""
        try:
            await self.storage.set(f"task:{task.task_id}", task)
            return True
        except Exception:
            return False
    
    async def dequeue(self) -> Optional[ScheduledTask]:
        """出队 (按优先级)"""
        # 实际实现需要存储后端支持优先级队列
        pass
    
    async def requeue(self, task: ScheduledTask) -> bool:
        """重新入队"""
        return await self.enqueue(task)
    
    async def remove(self, task_id: str) -> bool:
        """移除任务"""
        try:
            await self.storage.delete(f"task:{task_id}")
            return True
        except Exception:
            return False


# ============ 使用示例 ============

async def example_usage():
    """使用示例"""
    
    # 创建调度器
    scheduler = TaskScheduler(
        max_concurrent=5,
        default_timeout=60,
        default_max_retries=2,
        rate_limit=10,  # 10 req/s
        rate_burst=20,
    )
    
    # 进度回调
    def on_progress(task_id, status, meta):
        print(f"  进度: {task_id} -> {status.value} {meta}")
    
    def on_complete(result):
        print(f"  完成: {result.task_id} -> {result.status.value} ({result.duration:.2f}s)")
    
    scheduler.set_progress_callback(on_progress)
    scheduler.set_completion_callback(on_complete)
    
    # 定义任务
    async def scan_task(target: str, depth: int = 1):
        print(f"    执行扫描: {target} (depth={depth})")
        await asyncio.sleep(0.5)  # 模拟工作
        return {"target": target, "found": ["sub1", "sub2"]}
    
    async def stress_task(url: str):
        print(f"    压力测试: {url}")
        await asyncio.sleep(0.3)
        return {"url": url, "qps": 1000}
    
    # 调度任务
    print("调度任务...")
    
    # 高优先级立即执行
    scheduler.schedule(
        lambda: scan_task("example.com", 2),
        priority=TaskPriority.HIGH,
        tags=["scan", "priority"],
    )
    
    # 普通任务
    scheduler.schedule(
        lambda: scan_task("test.example.com", 1),
        priority=TaskPriority.NORMAL,
        tags=["scan"],
    )
    
    # 延迟任务
    scheduler.schedule(
        lambda: stress_task("http://example.com"),
        priority=TaskPriority.LOW,
        delay=2.0,
        tags=["stress"],
    )
    
    # 启动调度器
    await scheduler.start()
    
    # 等待所有完成
    await asyncio.sleep(5)
    
    # 显示结果
    print("\n=== 任务结果 ===")
    for tid, result in scheduler.get_all_results().items():
        print(f"  {tid}: {result.status.value} - {result.error or 'OK'}")
    
    print(f"\n统计: {scheduler.stats}")
    
    await scheduler.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())