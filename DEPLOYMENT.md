# QuantDinger 部署指南

## 目录

- [环境要求](#环境要求)
- [快速部署](#快速部署)
- [配置说明](#配置说明)
- [启动与停止](#启动与停止)
- [新设备部署](#新设备部署)
- [常见问题](#常见问题)

---

## 环境要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| **Docker Desktop** | 20.0+ | 容器运行环境 |
| **Docker Compose** | v2.0+ | 容器编排工具 |
| **Git** | 2.0+ | 代码克隆（可选） |
| **Python** | 3.8+ | SMTP代理服务（可选） |

### 系统支持

- Windows 10/11 + WSL2
- macOS 10.15+
- Ubuntu 20.04+

---

## 快速部署

### 第一步：克隆项目

```bash
# 方式一：直接克隆
git clone https://github.com/brokermr810/QuantDinger.git
cd QuantDinger


前端  https://github.com/brokermr810/QuantDinger
后端  https://github.com/brokermr810/QuantDinger.git
# 方式二：国内镜像加速
git clone https://github.com.cnpmjs.org/brokermr810/QuantDinger.git
cd QuantDinger
```

### 第二步：配置环境变量

```bash
# 进入后端目录
cd backend_api_python

# 复制环境变量模板
cp env.example .env

# 生成密钥（重要！）
python -c "import secrets; print(secrets.token_hex(32))"

# 编辑 .env 文件，将生成的密钥填入 SECRET_KEY
```

### 第三步：启动服务

```bash
# 返回项目根目录
cd ..

# 拉取镜像并启动
docker compose pull
docker compose up -d
```

### 第四步：访问服务

- **Web UI**: http://localhost:8888
- **API**: http://localhost:5000
- **默认账号**: `quantdinger` / `123456`

---

## 配置说明

### 核心配置文件

| 文件 | 说明 |
|------|------|
| `backend_api_python/.env` | 后端环境变量 |
| `docker-compose.yml` | Docker 编排配置 |
| `.env` (项目根目录) | Docker Compose 变量（可选） |

### 必须配置项

```bash
# backend_api_python/.env

# 安全密钥（必须修改！）
SECRET_KEY=你生成的64位随机字符串

# 数据库密码（建议修改）
POSTGRES_PASSWORD=你的数据库密码
```

### 可选配置项

#### 1. 镜像加速（国内用户）

```bash
# backend_api_python/.env
IMAGE_PREFIX=docker.m.daocloud.io/library/
```

#### 2. A股市场支持

```bash
# backend_api_python/.env
SHOW_CN_STOCK=true
```

#### 3. 支付功能（可选）

```bash
# backend_api_python/.env
USDT_PAY_ENABLED=true
USDT_PAY_ENABLED_CHAINS=TRC20
USDT_TRC20_ADDRESS=你的TRC20钱包地址
```

#### 4. 邮件服务（见下方详细配置）

---

## 邮件服务配置

### 方式一：直接配置（服务器部署推荐）

适用于：云服务器、VPS、有公网IP的环境

```bash
# backend_api_python/.env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=你的QQ邮箱@qq.com
SMTP_PASSWORD=你的授权码（不是QQ密码）
SMTP_FROM=你的QQ邮箱@qq.com
SMTP_USE_SSL=True
SMTP_USE_TLS=False
```

**获取QQ邮箱授权码：**

1. 登录 QQ邮箱 → 设置 → 账户
2. 找到 **POP3/SMTP服务**，点击开启
3. 验证身份（短信验证）
4. 获取16位授权码
5. 将授权码填入 `SMTP_PASSWORD`

### 方式二：SMTP代理（Windows本地开发推荐）

适用于：Docker Desktop for Windows、本地开发环境

**问题原因：** Docker Desktop for Windows 的容器无法直接访问外网 SMTP 服务器。

**解决方案：** 在宿主机运行 SMTP 代理服务。

#### 步骤1：修改配置

```bash
# backend_api_python/.env
# SMTP_HOST=192.168.0.30  # 宿主机IP
# SMTP_PORT=2525
# SMTP_USER=你的QQ邮箱@qq.com
# SMTP_PASSWORD=你的授权码
# SMTP_FROM=你的QQ邮箱@qq.com
# SMTP_USE_SSL=False
# SMTP_USE_TLS=False
$env:SMTP_HOST='192.168.0.30'
$env:SMTP_PORT='2525'
$env:SMTP_USER='2249808564@qq.com'
$env:SMTP_PASSWORD='mmfqrmyrawmbdiic'  # 在QQ邮箱设置中获取
$env:SMTP_FROM='2249808564@qq.com'
$env:SMTP_USE_TLS='false'
$env:SMTP_USE_SSL='false'
```

#### 步骤2：创建代理脚本

创建文件 `smtp_proxy.py`：

```python
#!/usr/bin/env python3
"""
Simple SSL SMTP Proxy
将非SSL连接转发到QQ邮箱SSL SMTP服务器
"""

import socket
import ssl
import threading

# 配置
LOCAL_HOST = '0.0.0.0'
LOCAL_PORT = 2525

# QQ邮箱SMTP配置
REMOTE_HOST = 'smtp.qq.com'
REMOTE_PORT = 465

def handle_client(client_socket, client_address):
    """处理客户端连接"""
    print(f"Connection from {client_address}")
    
    remote_socket = None
    
    try:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(30)
        
        context = ssl.create_default_context()
        remote_ssl = context.wrap_socket(remote_socket, server_hostname=REMOTE_HOST)
        remote_ssl.connect((REMOTE_HOST, REMOTE_PORT))
        
        print(f"Connected to {REMOTE_HOST}:{REMOTE_PORT}")
        
        def forward(source, destination, name):
            try:
                while True:
                    data = source.recv(4096)
                    if not data:
                        break
                    destination.sendall(data)
            except:
                pass
            finally:
                try:
                    source.close()
                except:
                    pass
                try:
                    destination.close()
                except:
                    pass
        
        t1 = threading.Thread(target=forward, args=(client_socket, remote_ssl, "C->S"))
        t2 = threading.Thread(target=forward, args=(remote_ssl, client_socket, "S->C"))
        
        t1.daemon = True
        t2.daemon = True
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if remote_socket:
            try:
                remote_socket.close()
            except:
                pass
        try:
            client_socket.close()
        except:
            pass

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server.bind((LOCAL_HOST, LOCAL_PORT))
    server.listen(10)
    
    print(f"SSL SMTP Proxy listening on {LOCAL_HOST}:{LOCAL_PORT}")
    print(f"Forwarding to {REMOTE_HOST}:{REMOTE_PORT}")
    
    try:
        while True:
            client_socket, client_address = server.accept()
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.close()

if __name__ == '__main__':
    start_server()
```

#### 步骤3：一键启动（推荐）

双击运行 `启动SMTP代理.bat` 即可自动启动代理服务。

#### 步骤4：启动代理服务

```bash
# 前台运行（可看日志）
python smtp_proxy.py

# 后台运行（Windows PowerShell）
Start-Process python -ArgumentList "smtp_proxy.py" -WindowStyle Hidden

# 后台运行（Linux/macOS）
nohup python smtp_proxy.py &
```

#### 步骤4：重启Docker服务

```bash
docker compose down
docker compose up -d
```

---

## 启动与停止

### 启动服务

```bash
# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend
```

### 停止服务

```bash
# 停止所有服务
docker compose down

# 停止并删除数据卷（清空数据）
docker compose down -v
```

### 重启服务

```bash
# 重启所有服务
docker compose restart

# 仅重启后端
docker compose restart backend
```

### 更新服务

```bash
# 拉取最新镜像
docker compose pull

# 重新创建容器
docker compose up -d
```

---

## 新设备部署

### 完整部署流程

#### 1. 安装 Docker Desktop

**Windows:**

```powershell
# 使用 winget 安装
winget install Docker.DockerDesktop

# 或手动下载安装
# https://www.docker.com/products/docker-desktop
```

**macOS:**

```bash
# 使用 Homebrew 安装
brew install --cask docker

# 或手动下载安装
# https://www.docker.com/products/docker-desktop
```

**Ubuntu:**

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
sudo apt install docker-compose-plugin

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER
```

#### 2. 克隆项目

```bash
git clone https://github.com/brokermr810/QuantDinger.git
cd QuantDinger
```

#### 3. 配置环境

```bash
# 复制配置模板
cp backend_api_python/env.example backend_api_python/.env

# 编辑配置
nano backend_api_python/.env  # Linux/macOS
notepad backend_api_python/.env  # Windows
```

**必须修改的配置：**

```bash
# 生成并设置密钥
SECRET_KEY=运行 python -c "import secrets; print(secrets.token_hex(32))" 生成

# 数据库密码
POSTGRES_PASSWORD=你的密码

# 启用A股
SHOW_CN_STOCK=true
```

#### 4. 启动服务

```bash
# 拉取镜像
docker compose pull

# 启动服务
docker compose up -d

# 检查状态
docker compose ps
```

#### 5. 验证部署

```bash
# 检查后端健康状态
curl http://localhost:5000/api/health

# 访问 Web UI
# 浏览器打开 http://localhost:8888
```

### 迁移数据（可选）

如果要从旧设备迁移数据：

```bash
# 旧设备导出数据
docker compose exec postgres pg_dump -U quantdinger quantdinger > backup.sql

# 新设备导入数据
docker compose cp backup.sql postgres:/backup.sql
docker compose exec postgres psql -U quantdinger quantdinger -f /backup.sql
```

---

## 常见问题

### 1. 容器无法启动

**检查日志：**

```bash
docker compose logs backend
```

**常见原因：**

- `SECRET_KEY` 未配置或使用默认值
- 端口被占用（5000/8888）
- 数据库未就绪

### 2. A股市场不显示

**解决方案：**

```bash
# backend_api_python/.env
SHOW_CN_STOCK=true
```

重启后端：

```bash
docker compose restart backend
```

### 3. 邮件发送失败

**错误：`Connection refused` 或 `Timeout`**

- Docker 容器无法访问外网 SMTP
- 使用 [SMTP代理方式](#方式二smtp代理windows本地开发推荐)

**错误：`Authentication failed`**

- 检查授权码是否正确（不是QQ密码）
- 重新生成授权码

### 4. 镜像拉取慢

**解决方案：**

```bash
# backend_api_python/.env
IMAGE_PREFIX=docker.m.daocloud.io/library/
```

或使用其他镜像源：

| 镜像源 | 地址 |
|--------|------|
| DaoCloud | `docker.m.daocloud.io/library/` |
| 阿里云 | `registry.cn-hangzhou.aliyuncs.com/library/` |

### 5. 策略创建失败

**错误：`market_category not supported`**

修改配置：

```bash
# backend_api_python/app/services/broker_market_policy.py
LIVE_MARKET_CATEGORIES = {"Crypto", "USStock", "Forex", "CNStock"}
```

### 6. 数据库连接失败

**检查数据库状态：**

```bash
docker compose ps postgres
docker compose logs postgres
```

**重置数据库：**

```bash
docker compose down -v
docker compose up -d
```

---

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Frontend | 8888 | Web UI |
| Backend | 5000 | API |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存 |
| SMTP Proxy | 2525 | 邮件代理（可选） |

---

## 默认账号

| 账号类型 | 用户名 | 密码 |
|----------|--------|------|
| 管理员 | `quantdinger` | `123456` |

> ⚠️ **重要**: 首次登录后请立即修改默认密码！

---

## 技术支持

- **项目地址**: https://github.com/brokermr810/QuantDinger
- **问题反馈**: https://github.com/brokermr810/QuantDinger/issues

---

## 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-06-18 | v1.0 | 初始部署文档 |
