# 🚀 Quick Start Guide

## 方式一：本地安装（推荐开发）

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd LLM-TradeBot
```

### 2. 一键安装

```bash
chmod +x install.sh
./install.sh
```

安装脚本会自动：

- ✅ 检测 Python 版本（需要 3.11+）
- ✅ 创建虚拟环境
- ✅ 安装所有依赖
- ✅ 生成 `.env` 配置文件

### 3. 配置 API Keys

编辑 `.env` 文件，填入你的 API 密钥：

```bash
# Binance API
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_secret_key
BINANCE_TESTNET=true

# LLM API (DeepSeek)
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### 4. 一键启动

```bash
./start.sh
```

启动脚本会自动：

- ✅ 激活虚拟环境
- ✅ 检查环境变量
- ✅ 启动 Dashboard（默认测试模式）

访问 Dashboard: **<http://localhost:8000>**

---

## 方式二：Docker 部署（推荐生产）

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd LLM-TradeBot
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 API keys
```

### 3. 一键启动

```bash
cd docker
docker-compose up -d
```

### 4. 查看日志

```bash
docker-compose logs -f
```

### 5. 停止服务

```bash
docker-compose down
```

---

## 启动参数

### 本地启动

```bash
# 测试模式 + 持续运行
./start.sh --test --mode continuous

# 生产模式
./start.sh --mode continuous

# 单次运行
./start.sh --test
```

### Docker 启动

修改 `docker/docker-compose.yml` 中的 `CMD` 参数。

---

## 常见问题

### Q: Python 版本不符合要求？

**A**: 安装 Python 3.11+

- macOS: `brew install python@3.11`
- Ubuntu: `sudo apt install python3.11`

### Q: 依赖安装失败？

**A**: 确保已安装编译工具

- macOS: `xcode-select --install`
- Ubuntu: `sudo apt install build-essential`

### Q: Dashboard 无法访问？

**A**: 检查端口 8000 是否被占用

```bash
lsof -i :8000
```

### Q: Docker 构建失败？

**A**: 确保 Docker 已安装并运行

```bash
docker --version
docker-compose --version
```

---

## 目录结构

```
LLM-TradeBot/
├── install.sh          # 一键安装脚本
├── start.sh            # 一键启动脚本
├── main.py             # 主程序
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── src/                # 源代码
├── data/               # 数据目录
├── logs/               # 日志目录
└── web/                # Dashboard 前端
```

---

## 下一步

1. ✅ 访问 Dashboard: <http://localhost:8000>
2. ✅ 点击 "Start" 开始交易
3. ✅ 查看实时决策和分析

**祝交易顺利！** 🎉
