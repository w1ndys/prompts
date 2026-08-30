---
issue: 8
title: "[容器化部署] Docker 服务接入 Traefik 的 Compose 规范"
source: https://github.com/w1ndys/prompts/issues/8
state: closed
---

```
新服务 Docker 化及接入 Traefik 的统一规范

请按以下标准编写 docker-compose.yml，所有对外提供 Web 服务的容器都必须遵循此规范，其余内部服务（数据库、消息队列等）只需加入对应内部网络。

1. 网络要求
- 需要对外访问的服务容器必须加入预置的外部网络 traefik-public，并保留原有内部网络（如 app-net，如果没有就根据项目名命名一个具有代表性的名字）。
- 声明时按以下格式：

networks:
  traefik-public:
    external: true
  app-net:
    driver: bridge

2. 标签规范（核心）
必须在对外服务的容器上添加 5 条 Traefik 标签，格式如下：

labels:
  - "traefik.enable=true"
  - "traefik.http.routers.<服务名>.rule=Host(`<域名>`)"
  - "traefik.http.routers.<服务名>.entrypoints=websecure"
  - "traefik.http.routers.<服务名>.tls.certresolver=leresolver"
  - "traefik.http.services.<服务名>.loadbalancer.server.port=<容器内部端口>"

- <服务名> 用简短的英文标识，如 halo、wiki。
- <内部端口> 指容器内应用监听的端口（如 Nginx 用 80，Tomcat 用 8080，Spring Boot 用 8080 等）。

3. 端口映射
- 禁止在 Web 服务容器上使用 ports 将端口映射到宿主机，所有流量由 Traefik 代理。除非有特殊需求被提到，例如用于给内网纯ip访问，需要做一个端口映射从容器内映射到宿主机某个端口
- 数据库等内部服务如需宿主机调试，可临时加 ports 并限制访问 IP（如 127.0.0.1:3306:3306）。

4. 镜像选择
- 优先选择官方 alpine 或 slim 版本以减小体积。
- 若需要额外依赖，可使用 Dockerfile 构建，但需在 build 中指定上下文。

5. 重启策略：所有容器必须设置 restart: always（除非有特殊原因）。

6. 数据持久化：将需要保留的数据通过 volumes 挂载到宿主机目录（如 ./data:/app/data），不要写入容器可写层。

7. 环境变量与保密信息
- 使用 .env 文件存放通用变量，通过 env_file 引入。
- 敏感信息（密钥、密码）放在 .env 中并确保 .gitignore，或使用 Docker secrets（高阶）。

8. 健康检查（可选）
若应用支持，可添加健康检查，提高服务可用性：
注意健康检查必须使用curl命令不能使用wget命令，也不能使用localhost地址，必须使用127.0.0.1，防止localhost被解析到ipv6地址，如果是vue前端，必须用/index.html  不要用 /

healthcheck:
  test: ["CMD", "curl", "-f", "http://127.0.0.1:80/health"]
  interval: 30s
  timeout: 10s
  retries: 3

9. 完整模板示例（通用 Web 应用）

services:
  my-service:
    image: my-app:1.0-alpine        # 或 build: ./src
    container_name: my-service
    restart: always
    env_file: .env
    networks:
      - traefik-public
      - app-net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myservice.rule=Host(`<域名>`)"
      - "traefik.http.routers.myservice.entrypoints=websecure"
      - "traefik.http.routers.myservice.tls.certresolver=leresolver"
      - "traefik.http.services.myservice.loadbalancer.server.port=8080"
    volumes:
      - ./data:/app/data

networks:
  traefik-public:
    external: true
  app-net:
    driver: bridge
```
