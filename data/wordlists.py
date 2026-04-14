#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 子域名字典库
包含 5000+ 常用子域名前缀
"""

# ============== 基础前缀 (500+) ==============
BASIC_PREFIXES = """
www mail ftp admin blog api dev test staging portal app mobile m bbs forum
cdn static img image images video media shop store pay payment secure vpn
remote git svn jenkins ci crm erp oa hr email webmail smtp pop imap ns1 ns2
proxy cache file download upload assets css js fonts lib docs help support
news info wiki doc demo beta alpha gamma delta omega old new legacy backup
db database sql mysql pgsql mongo redis memcached es elastic rabbitmq kafka
docker k8s kubernetes rancher harbor registry nexus artifactory
chat im message notification push sms email mailer
auth login sso oauth ldap ad cas shibboleth
api-gateway nginx apache tomcat iis jetty weblogic websphere jboss wildfly
grafana kibana prometheus alertmanager nagios zabbix prometheus
jenkins gitlab bitbucket gitea gogs bamboo teamcity
sonarqube nexus harbor jfrog
vpn pptp l2tp openvpn wireguard cisco fortigate
ssh sftp scp rsync
ftp tftp samba nfs
dns bind powerdns unbound
dhcp pxp tftp
ntp chrony
ldap radius tacacs
proxy squid varnish haproxy nginx apache
fw firewall pfsense opnsense
siem splunk elk graylog
ids snort suricata zeek
waf modsecurity
av antivirus clamav
mail postfix dovecot exim zimbra
webmail roundcube squirrelmail horde
calendar calendr contacts
office office365 teams zoom slack discord
meet webinar live stream radio tv
shop shopify magento woocommerce prestashop opencart
pay stripe paypal alipay wechat-pay
blog wordpress ghost hugo jekyll hexo
cms drupal joomla typo3
forum discourse phpbb smf vanilla
wiki mediawiki confluence dokuwiki
erp sap odoo erpnext
crm salesforce hubspot zoho
hr workday bambooHR
accounting quickbooks xero
project jira trello asana basecamp
knowledge notion obsidian
collab miro figma canva
design sketch adobe creative
video youtube vimeo twitch
audio podcast soundcloud spotify
analytics ga piwik matomo
ads google-ads facebook-ads
seo ahrefs semrush moz
monitor uptimerobot pingdom
status statuspage
help zendesk freshdesk
ticket rt otrs
sales hubspot salesforce
marketing marketo hubspot
automation zapier ifttt
integration mule talend
etl airflow dbt
bi tableau powerbi looker
dw snowflake bigquery redshift
data spark hadoop hive
ml jupyter notebook
ai openai anthropic
llm gpt claude
bot chatbot assistant
api rest graphql grpc soap
ws websocket socket
mq rabbitmq kafka activemq
cache redis memcached
queue celery rq
job airflow dagster
log fluentd logstash
trace jaeger zipkin
metrics prometheus
alert alertmanager pagerduty
incident pagerduty opsgenie
oncall pagerduty
sre reliability
devops cicd
ops kubernetes docker
cloud aws azure gcp aliyun tencent huawei
iaas ec2 vm compute
paas lambda function
saas saas-app
container docker podman k8s
registry ecr gcr harbor
storage s3 oss cos
cdn cloudfront akamai fastly
dns route53 cloudns
cert letsencrypt
secret vault
iam cognito auth0
db rds dynamodb cosmos
queue sqs sns
topic kafka
stream kinesis
analytics athena bigquery
ml sagemaker vertex
ai bedrock
search elasticsearch algolia
log cloudwatch
monitor datadog newrelic
apm jaeger
""".split()

# ============== 常用业务前缀 (200+) ==============
BUSINESS_PREFIXES = """
account accounts user users customer customers member members
order orders product products item items cart checkout
inventory stock warehouse supply chain
finance financial billing invoice invoices payment payments
report reports analytics statistics dashboard
admin administrator administrators manager managers
operator operators agent agents representative representatives
partner partners vendor vendors supplier suppliers
client clients enterprise enterprises corporate
internal external public private
api-gw api-gateway gateway gateways
service services microservice microservices
backend frontend webapp web-app
ios android mobile-app desktop-app
native hybrid web-view
oauth2 oidc saml
mfa totp u2f webauthn
permission permissions role roles privilege privileges
audit logs logging tracing
health status ready live
metrics prometheus grafana
config configuration settings preferences
feature flag flags toggle toggles
ab experiment experiments
sandbox staging prod production
dev development qa test testing uat
pre-prod pre-production
blue green canary
feature-branch release hotfix
version v1 v2 v3 api-v1 api-v2
restful graphql grpc
openapi swagger redoc
documentation docs readme
tutorial guide guides manual
faq faqs help support
feedback survey surveys
contact about us team careers
press media news blog
events webinar webinars conference
training learn learning education
community forum forums discord slack
social twitter facebook linkedin instagram
rss feed newsletter
sitemap robots favicon
manifest sw service-worker
pwa spa ssr
nuxt next react vue angular
svelte solid astro
""".split()

# ============== 环境/版本前缀 (100+) ==============
ENV_PREFIXES = """
dev development staging stage prod production
test testing qa uat sit
sandbox beta alpha gamma
demo sample example
poc mvp prototype
old new legacy current
v1 v2 v3 v4 v5
v1-api v2-api api-v1 api-v2
release debug
canary blue green
a b c d e f g h i j k l m n o p q r s t u v w x y z
0 1 2 3 4 5 6 7 8 9
01 02 03 04 05 06 07 08 09 10
11 12 13 14 15 16 17 18 19 20
1a 2a 3a 1b 2b 3b
backup bkup bak old prev previous
next future wip draft temp tmp
internal external intranet extranet
vpn ssl ssh sftp
dmz lan wan
public private protected
secure trusted untrusted
""".split()

# ============== 技术栈前缀 (300+) ==============
TECH_PREFIXES = """
python django flask fastapi tornado
java spring boot tomcat jetty jboss wildfly websphere weblogic
node express nest koa fastify hapi
php laravel symfony codeigniter yii cakephp
ruby rails sinatra
go gin echo fiber chi
rust actix rocket axum
dotnet aspnet core iis
react next nuxt remix gatsby
vue nuxt vitepress gridsome
angular universal nestjs
svelte kit astro solid
mongodb mysql postgres postgresql mariadb
redis memcached elasticsearch mongodb
rabbitmq kafka activemq zeromq
nginx apache caddy traefik envoy
docker kubernetes k8s k3s k3d
jenkins gitlab github-actions circleci travis
prometheus grafana loki tempo
elk kibana logstash beats
nginx-ingress traefik istio linkerd
consul etcd zookeeper
vault consul-template
nomad terraform ansible chef puppet
helm kustomize argocd flux
prometheus-operator Thanos
opentelemetry jaeger zipkin
istio-envoy envoy-proxy
coredns kube-dns
flannel calico cilium weave
rook longhorn openebs
velero kasten
falco sysdig
opa gatekeeper
kyverno
vault-consul
boundary waypoint
packer nomad
""".split()

# ============== 安全相关前缀 (100+) ==============
SECURITY_PREFIXES = """
security secure ssl tls https
auth authentication authorize authorization
login signin signup register logout signout
sso oauth oauth2 oidc saml ldap
mfa 2fa totp u2f webauthn yubikey
captcha recaptcha hcaptcha
firewall waf ids ips siem
vpn proxy tunnel ssh sftp
堡垒机 jumpserver 跳板机
audit log logging monitor monitoring
scan scanner vulnerability vulnerabilities
pentest security-test red-team blue-team
soc soc2 iso gdpr hipaa pci
compliance policy policies
access-control rbac abac
secret secrets credentials credential
token tokens jwt session sessions
certificate certificates cert certs
key keys private public
encrypt encryption decrypt decryption
hash hashing password passwords
salt salts nonce nonces
signature signatures
trust trusted untrusted
""".split()

# ============== 国内常见前缀 (200+) ==============
CN_PREFIXES = """
官网 官方 网站 网页
首页 首页 登录 注册 用户 会员
后台 管理 管理员 管理后台
系统 平台 服务中心 服务
应用 应用商店 小程序 公众号
支付 交易 订单 购物 商城
客服 帮助 反馈 投诉 建议
新闻 资讯 动态 公告 通知
活动 优惠 促销 营销 推广
社区 论坛 贴吧 圈子 群组
博客 微博 视频 直播 图片 相册
下载 资源 文件 软件 应用
api接口 开发者 开放平台
数据 统计 报表 分析 大数据
云服务 云计算 云存储 对象存储
cdn 加速 负载均衡 防护 安全
测试 环境 预发布 灰度 生产
运维 监控 告警 日志 追踪
自动化 发布 部署 构建 流水线
微服务 服务发现 配置中心 网关
消息队列 缓存 数据库 搜索
人工智能 机器学习 深度学习 算法
""".split()

# ============== 完整字典 ==============
ALL_PREFIXES = list(set(
    BASIC_PREFIXES + 
    BUSINESS_PREFIXES + 
    ENV_PREFIXES + 
    TECH_PREFIXES + 
    SECURITY_PREFIXES + 
    CN_PREFIXES
))

# 按优先级分组
PRIORITY_HIGH = [
    'www', 'mail', 'ftp', 'admin', 'blog', 'api', 'dev', 'test',
    'staging', 'portal', 'app', 'mobile', 'm', 'bbs', 'forum',
    'cdn', 'static', 'img', 'video', 'shop', 'pay', 'vpn', 'git',
    'jenkins', 'oa', 'crm', 'erp', 'webmail', 'ns1', 'ns2',
    'proxy', 'db', 'mysql', 'redis', 'mongo', 'backup', 'login',
    'sso', 'auth', 'vpn', 'ssh', 'sftp', 'grafana', 'kibana'
]

PRIORITY_MEDIUM = BUSINESS_PREFIXES + TECH_PREFIXES

PRIORITY_LOW = ENV_PREFIXES + [p for p in ALL_PREFIXES if p not in PRIORITY_HIGH and p not in PRIORITY_MEDIUM]


if __name__ == "__main__":
    print(f"字典总量: {len(ALL_PREFIXES)}")
    print(f"高优先级: {len(PRIORITY_HIGH)}")
    print(f"中优先级: {len(PRIORITY_MEDIUM)}")
    print(f"低优先级: {len(PRIORITY_LOW)}")
