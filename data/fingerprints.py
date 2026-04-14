#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - Web指纹库
包含 200+ Web应用指纹
"""

# ============== CMS指纹 ==============
CMS_FINGERPRINTS = {
    # 国内CMS
    "WordPress": {
        "html": ["wp-content", "wp-includes", "wp-json", "wp-login.php"],
        "headers": ["X-Pingback"],
        "meta": ["WordPress"],
        "url": ["/wp-login.php", "/wp-admin/"]
    },
    "Drupal": {
        "html": ["Drupal.settings", "drupal.js", "Drupal"],
        "headers": ["X-Drupal-Cache", "X-Generator: Drupal"],
        "meta": ["Drupal"],
        "url": ["/user/login", "/sites/default/files/"]
    },
    "Joomla": {
        "html": ["Joomla", "option=com_", "Joomla!"],
        "headers": ["X-Powered-By: Joomla"],
        "meta": ["Joomla"],
        "url": ["/administrator/"]
    },
    "Discuz!": {
        "html": ["Discuz", "discuz_uid", "dz_footer"],
        "headers": ["Set-Cookie: discuz"],
        "meta": [],
        "url": ["/forum.php", "/member.php"]
    },
    "DedeCMS": {
        "html": ["dedecms", "dedeajax", "DedeCMS"],
        "headers": [],
        "meta": [],
        "url": ["/dede/", "/plus/"]
    },
    "PhpWind": {
        "html": ["phpwind", "windid", "PhpWind"],
        "headers": [],
        "meta": [],
        "url": ["/windid/"]
    },
    "ThinkCMF": {
        "html": ["thinkcmf", "ThinkCMF"],
        "headers": [],
        "meta": [],
        "url": ["/portal/"]
    },
    "PHPCMS": {
        "html": ["phpcms", "PHPCMS"],
        "headers": [],
        "meta": [],
        "url": ["/phpcms/"]
    },
    "帝国CMS": {
        "html": ["EmpireCMS", "帝国CMS", "e/admin"],
        "headers": [],
        "meta": [],
        "url": ["/e/admin/"]
    },
    "Z-Blog": {
        "html": ["Z-Blog", "zb_user", "Z-BlogPHP"],
        "headers": [],
        "meta": ["Z-Blog"],
        "url": ["/zb_users/"]
    },
    "Typecho": {
        "html": ["typecho", "Typecho"],
        "headers": [],
        "meta": [],
        "url": ["/admin/"]
    },
    "Ghost": {
        "html": ["ghost-url", "Ghost"],
        "headers": ["X-Powered-By: Ghost"],
        "meta": [],
        "url": ["/ghost/"]
    },
    "Hugo": {
        "html": ["Hugo", "hugo-generator"],
        "headers": [],
        "meta": [],
        "url": []
    },
}

# ============== 开发框架指纹 ==============
FRAMEWORK_FINGERPRINTS = {
    "Django": {
        "html": ["csrfmiddlewaretoken", "django", "DJANGO"],
        "headers": ["X-Frame-Options", "csrftoken"],
        "cookies": ["csrftoken", "sessionid"],
        "url": ["/admin/", "/static/admin/"]
    },
    "Flask": {
        "html": ["Werkzeug", "flask", "Flask"],
        "headers": ["Server: Werkzeug"],
        "cookies": [],
        "url": []
    },
    "Spring": {
        "html": ["Whitelabel Error Page", "springframework"],
        "headers": ["X-Application-Context"],
        "cookies": ["JSESSIONID"],
        "url": ["/actuator/", "/actuator/health"]
    },
    "Spring Boot": {
        "html": ["Whitelabel Error Page"],
        "headers": [],
        "cookies": [],
        "url": ["/actuator/"]
    },
    "Laravel": {
        "html": ["laravel", "Laravel", "csrf-token"],
        "headers": ["Set-Cookie: laravel_session"],
        "cookies": ["laravel_session", "XSRF-TOKEN"],
        "url": []
    },
    "Express.js": {
        "html": ["Express", "express"],
        "headers": ["X-Powered-By: Express"],
        "cookies": [],
        "url": []
    },
    "Next.js": {
        "html": ["__NEXT_DATA__", "_next/"],
        "headers": ["x-nextjs-cache"],
        "cookies": [],
        "url": ["/_next/"]
    },
    "Nuxt.js": {
        "html": ["__NUXT__", "_nuxt/"],
        "headers": [],
        "cookies": [],
        "url": ["/_nuxt/"]
    },
    "Vue.js": {
        "html": ["vue", "Vue", "__vue__", "data-v-"],
        "headers": [],
        "cookies": [],
        "url": []
    },
    "React": {
        "html": ["react", "React", "_reactRootContainer", "data-reactroot"],
        "headers": [],
        "cookies": [],
        "url": []
    },
    "Angular": {
        "html": ["ng-version", "ng-app", "angular", "Angular"],
        "headers": [],
        "cookies": [],
        "url": []
    },
    "ASP.NET": {
        "html": ["__VIEWSTATE", "ASP.NET", "aspNetHidden"],
        "headers": ["X-AspNet-Version", "X-Powered-By: ASP.NET"],
        "cookies": ["ASP.NET_SessionId"],
        "url": []
    },
    "Ruby on Rails": {
        "html": ["rails", "Rails", "csrf-param"],
        "headers": ["X-Runtime", "X-Powered-By: Phusion Passenger"],
        "cookies": ["_session_id"],
        "url": []
    },
    "Gin": {
        "html": [],
        "headers": [],
        "cookies": [],
        "url": []
    },
    "FastAPI": {
        "html": ["FastAPI", "swagger-ui", "openapi.json"],
        "headers": [],
        "cookies": [],
        "url": ["/docs", "/openapi.json"]
    },
    "ThinkPHP": {
        "html": ["ThinkPHP", "think_var"],
        "headers": ["X-Powered-By: ThinkPHP"],
        "cookies": [],
        "url": []
    },
    "CodeIgniter": {
        "html": ["CodeIgniter", "ci_session"],
        "headers": [],
        "cookies": ["ci_session"],
        "url": []
    },
    "Yii": {
        "html": ["Yii", "yii", "CSRF_TOKEN"],
        "headers": [],
        "cookies": [],
        "url": []
    },
}

# ============== 前端框架指纹 ==============
FRONTEND_FINGERPRINTS = {
    "Bootstrap": {
        "html": ["bootstrap", "Bootstrap", "btn-primary"],
        "css": ["bootstrap.css", "bootstrap.min.css"]
    },
    "TailwindCSS": {
        "html": ["tailwind", "tw-", "bg-", "text-", "flex"],
        "css": ["tailwind.css"]
    },
    "jQuery": {
        "html": ["jquery", "jQuery", "$()"],
        "js": ["jquery.js", "jquery.min.js"]
    },
    "Element UI": {
        "html": ["el-", "element-ui", "Element UI"],
        "css": ["element-ui.css"]
    },
    "Ant Design": {
        "html": ["ant-", "ant-design", "Ant Design"],
        "css": ["antd.css"]
    },
    "Vuetify": {
        "html": ["v-", "vuetify", "Vuetify"],
        "css": ["vuetify.css"]
    },
    "Material UI": {
        "html": ["MuiBox", "MuiButton", "material-ui"],
        "css": []
    },
}

# ============== 中间件指纹 ==============
MIDDLEWARE_FINGERPRINTS = {
    "Nginx": {
        "headers": ["Server: nginx", "Server: Nginx"],
        "html": ["nginx", "Nginx"],
        "status_pages": ["/nginx_status"]
    },
    "Apache": {
        "headers": ["Server: Apache"],
        "html": ["Apache"],
        "status_pages": ["/server-status", "/server-info"]
    },
    "Tomcat": {
        "html": ["Apache Tomcat", "Tomcat", "manager/html"],
        "headers": [],
        "status_pages": ["/manager/html", "/manager/status"]
    },
    "IIS": {
        "headers": ["Server: Microsoft-IIS"],
        "html": ["IIS", "Microsoft-IIS"],
        "status_pages": []
    },
    "Jetty": {
        "headers": ["Server: Jetty"],
        "html": ["Jetty"],
        "status_pages": []
    },
    "WebLogic": {
        "html": ["WebLogic", "bea-", "wls-"],
        "headers": [],
        "status_pages": ["/console/", "/wls-wsat/"]
    },
    "WebSphere": {
        "html": ["WebSphere", "IBM"],
        "headers": [],
        "status_pages": ["/ibm/console/"]
    },
    "JBoss": {
        "html": ["JBoss", "jboss"],
        "headers": [],
        "status_pages": ["/jmx-console/", "/web-console/"]
    },
    "WildFly": {
        "html": ["WildFly", "wildfly"],
        "headers": [],
        "status_pages": ["/management/"]
    },
    "GlassFish": {
        "html": ["GlassFish", "glassfish"],
        "headers": [],
        "status_pages": ["/admin/"]
    },
    "Caddy": {
        "headers": ["Server: Caddy"],
        "html": [],
        "status_pages": []
    },
    "Traefik": {
        "headers": ["Server: traefik"],
        "html": [],
        "status_pages": ["/dashboard/"]
    },
    "OpenResty": {
        "headers": ["Server: openresty"],
        "html": [],
        "status_pages": []
    },
    "Tengine": {
        "headers": ["Server: Tengine"],
        "html": [],
        "status_pages": []
    },
}

# ============== 数据库指纹 ==============
DATABASE_FINGERPRINTS = {
    "MySQL": {
        "port": 3306,
        "banner": ["MySQL", "MariaDB"],
        "error_patterns": ["mysql_", "MySQL", "MariaDB"]
    },
    "PostgreSQL": {
        "port": 5432,
        "banner": ["PostgreSQL"],
        "error_patterns": ["pg_", "PostgreSQL"]
    },
    "MongoDB": {
        "port": 27017,
        "banner": ["MongoDB"],
        "error_patterns": ["mongo", "MongoDB"]
    },
    "Redis": {
        "port": 6379,
        "banner": ["Redis"],
        "error_patterns": ["NOAUTH", "Redis"]
    },
    "Elasticsearch": {
        "port": 9200,
        "banner": ["Elasticsearch"],
        "error_patterns": ["elasticsearch", "lucene"]
    },
    "Memcached": {
        "port": 11211,
        "banner": ["Memcached"],
        "error_patterns": []
    },
    "MSSQL": {
        "port": 1433,
        "banner": ["Microsoft SQL Server"],
        "error_patterns": ["mssql", "SQL Server"]
    },
    "Oracle": {
        "port": 1521,
        "banner": ["Oracle"],
        "error_patterns": ["ORA-", "Oracle"]
    },
}

# ============== 安全组件指纹 ==============
SECURITY_FINGERPRINTS = {
    "Shiro": {
        "html": [],
        "headers": [],
        "cookies": ["rememberMe"],
        "url": []
    },
    "Spring Security": {
        "html": ["login", "password"],
        "headers": [],
        "cookies": ["JSESSIONID"],
        "url": ["/login"]
    },
    "WAF-CloudFlare": {
        "headers": ["cf-ray", "cloudflare", "cf-cache-status"],
        "html": [],
        "cookies": [],
        "url": []
    },
    "WAF-Akamai": {
        "headers": ["akamai", "x-akamai"],
        "html": [],
        "cookies": [],
        "url": []
    },
    "WAF-ModSecurity": {
        "headers": [],
        "html": ["ModSecurity", "mod_security"],
        "cookies": [],
        "url": []
    },
    "WAF-安全狗": {
        "headers": [],
        "html": ["安全狗", "safedog"],
        "cookies": [],
        "url": []
    },
    "WAF-云盾": {
        "headers": [],
        "html": ["云盾", "aliyun"],
        "cookies": [],
        "url": []
    },
    "宝塔面板": {
        "headers": [],
        "html": ["宝塔", "BaoTa", "bt.cn"],
        "cookies": [],
        "url": ["/:8888/", "/admin/"]
    },
    "phpMyAdmin": {
        "html": ["phpMyAdmin", "pma_username", "phpmyadmin"],
        "headers": [],
        "cookies": ["phpMyAdmin"],
        "url": ["/phpmyadmin/", "/pma/"]
    },
    "Adminer": {
        "html": ["Adminer", "adminer"],
        "headers": [],
        "cookies": [],
        "url": ["/adminer.php"]
    },
}

# ============== DevOps工具指纹 ==============
DEVOPS_FINGERPRINTS = {
    "Jenkins": {
        "html": ["Jenkins", "jenkins"],
        "headers": ["X-Jenkins"],
        "cookies": [],
        "url": ["/login", "/jenkins/"]
    },
    "GitLab": {
        "html": ["GitLab", "gitlab"],
        "headers": [],
        "cookies": ["_gitlab_session"],
        "url": ["/users/sign_in"]
    },
    "Gitea": {
        "html": ["Gitea", "gitea"],
        "headers": [],
        "cookies": [],
        "url": ["/user/login"]
    },
    "Gogs": {
        "html": ["Gogs", "gogs"],
        "headers": [],
        "cookies": [],
        "url": ["/user/login"]
    },
    "SonarQube": {
        "html": ["SonarQube", "sonar"],
        "headers": [],
        "cookies": [],
        "url": ["/sessions/login"]
    },
    "Nexus": {
        "html": ["Nexus", "nexus"],
        "headers": [],
        "cookies": [],
        "url": ["/nexus/"]
    },
    "Harbor": {
        "html": ["Harbor", "harbor"],
        "headers": [],
        "cookies": [],
        "url": ["/harbor/sign-in"]
    },
    "Docker Registry": {
        "html": ["Docker", "registry"],
        "headers": [],
        "cookies": [],
        "url": ["/v2/"]
    },
    "Rancher": {
        "html": ["Rancher", "rancher"],
        "headers": [],
        "cookies": [],
        "url": ["/login"]
    },
    "Kubernetes Dashboard": {
        "html": ["Kubernetes", "kubernetes"],
        "headers": [],
        "cookies": [],
        "url": ["/api/v1/login"]
    },
    "ArgoCD": {
        "html": ["ArgoCD", "argocd"],
        "headers": [],
        "cookies": [],
        "url": ["/login"]
    },
    "Grafana": {
        "html": ["Grafana", "grafana"],
        "headers": [],
        "cookies": ["grafana_sess"],
        "url": ["/login"]
    },
    "Kibana": {
        "html": ["Kibana", "kibana"],
        "headers": [],
        "cookies": ["kbn-xpack-sig"],
        "url": ["/app/kibana"]
    },
    "Prometheus": {
        "html": ["Prometheus", "prometheus"],
        "headers": [],
        "cookies": [],
        "url": ["/graph", "/metrics"]
    },
    "Zabbix": {
        "html": ["Zabbix", "zabbix"],
        "headers": [],
        "cookies": [],
        "url": ["/zabbix/"]
    },
}

# ============== 合并所有指纹 ==============
ALL_FINGERPRINTS = {
    **CMS_FINGERPRINTS,
    **FRAMEWORK_FINGERPRINTS,
    **FRONTEND_FINGERPRINTS,
    **MIDDLEWARE_FINGERPRINTS,
    **SECURITY_FINGERPRINTS,
    **DEVOPS_FINGERPRINTS,
}


if __name__ == "__main__":
    print(f"指纹总量: {len(ALL_FINGERPRINTS)}")
    print(f"CMS: {len(CMS_FINGERPRINTS)}")
    print(f"框架: {len(FRAMEWORK_FINGERPRINTS)}")
    print(f"中间件: {len(MIDDLEWARE_FINGERPRINTS)}")
    print(f"安全组件: {len(SECURITY_FINGERPRINTS)}")
    print(f"DevOps: {len(DEVOPS_FINGERPRINTS)}")
