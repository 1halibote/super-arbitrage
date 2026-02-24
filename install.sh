#!/bin/bash
# ==========================================================
# 自动化套利交易机器人安装向导 (Astro 风格)
# 用法: curl -sSL https://raw.githubusercontent.com/1halibote/super-arbitrage/refs/heads/main/install.sh | sudo bash -
# ==========================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 镜像与安装信息定制区域
IMAGE_NAME="crpi-mgnzs1jjf6ptpiqf.ap-northeast-1.personal.cr.aliyuncs.com/super-arbitrage/bn-by-bot:latest"
CONTAINER_NAME="bn-by-bot"
NGINX_CONTAINER="bn-by-nginx"

# 默认设置
INSTALL_PORT=20003
INSTALL_PATH="/PkRsdefefaw/dashboard"
LICENSE_KEY=""

log_info() { echo -e "${GREEN}[INSTALL]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. 欢迎信息与输入参数
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}   🚀 欢迎使用自动化套利交易系统一键安装向导 ${NC}"
echo -e "${GREEN}=====================================================${NC}"

echo -n -e "请输入您的机器授权码 (License Key): "
read input_key < /dev/tty
if [ -n "$input_key" ]; then LICENSE_KEY=$input_key; fi

echo -n -e "请输入您想要绑定的访问端口 (默认 $INSTALL_PORT): "
read input_port < /dev/tty
if [ -n "$input_port" ]; then INSTALL_PORT=$input_port; fi

echo -n -e "请输入您的安全访问后缀 (默认 $INSTALL_PATH): "
read input_path < /dev/tty
if [ -n "$input_path" ]; then 
    if [[ $input_path != /* ]]; then INSTALL_PATH="/$input_path"; else INSTALL_PATH=$input_path; fi
fi

# 工具函数
generate_2fa_secret() {
    local base32_chars="ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    local secret=""
    for i in $(seq 1 32); do secret="${secret}${base32_chars:RANDOM%32:1}"; done
    echo "$secret"
}

# 初始化 2FA 密钥 (持久化存储，防止重装丢失)
AUTH_DIR="/opt/bn-by-bot"
AUTH_FILE="$AUTH_DIR/auth.secret"
mkdir -p "$AUTH_DIR"
if [ -f "$AUTH_FILE" ]; then
    GOOGLE_AUTH_SECRET=$(cat "$AUTH_FILE")
    log_info "✅ 从本地恢复了已有的 Google 2FA 密钥。"
else
    GOOGLE_AUTH_SECRET=$(generate_2fa_secret)
    echo "$GOOGLE_AUTH_SECRET" > "$AUTH_FILE"
    log_info "🆕 已为您自动生成独家高强度的 Google 2FA 的密钥。"
fi

# 2. 检查与安装 Docker
if ! command -v docker &> /dev/null; then
    log_warn "未检测到 Docker 环境，正在为您自动安装..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
    rm get-docker.sh
    log_info "Docker 环境初始化成功！"
fi

# 3. 安装依赖工具
log_info "安装辅助工具..."
if command -v apt-get &> /dev/null; then
    apt-get update -y > /dev/null 2>&1
    apt-get install -y qrencode curl > /dev/null 2>&1
elif command -v yum &> /dev/null; then
    yum install -y qrencode curl > /dev/null 2>&1
fi

# 4. 获取公网 IP
DETECTED_IP=$(curl -s ifconfig.me)
log_info "Detected public IP: $DETECTED_IP"
echo -n -e "\n${YELLOW}----> [INSTALL] Use this IP? [Y/n] ${NC}"
read ip_confirm < /dev/tty
if [[ "$ip_confirm" == "n" || "$ip_confirm" == "N" ]]; then
    echo -n -e "请输入您指定的云服务器外网 IP 或 独立域名: "
    read SERVER_IP < /dev/tty
else
    SERVER_IP=$DETECTED_IP
fi

# 5. 部署核心系统引擎
log_info "拉取核心加密交易引擎镜像..."
docker pull $IMAGE_NAME

if docker ps -a | grep -q $CONTAINER_NAME; then
    log_info "发现旧进程，正在为您清理与覆盖..."
    docker rm -f $CONTAINER_NAME
fi

log_info "启动底盘交易引擎中..."
docker run -d \
    --name $CONTAINER_NAME \
    --restart always \
    -e LICENSE_KEY="$LICENSE_KEY" \
    -e GOOGLE_AUTH_SECRET="$GOOGLE_AUTH_SECRET" \
    $IMAGE_NAME

# 6. 配置 Nginx 动态反向代理 (解决白屏与路径漂移)
log_info "正在配置服务器 Nginx 防护网关..."
NGINX_DIR="/opt/bn-by-bot/nginx"
mkdir -p "$NGINX_DIR"
cat > "$NGINX_DIR/default.conf" <<EOF
server {
    listen $INSTALL_PORT;
    server_name _;

    # A. 兼容隐藏跳板链接访问，自动清洗为标准域
    location ^~ $INSTALL_PATH {
        return 301 \$scheme://\$host:\$server_port/;
    }

    # B. 静态资源直通专线
    location ~* ^/(_next|static|public|favicon\.ico) {
        proxy_pass http://$CONTAINER_NAME:3000;
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    # C. API 与 WebSocket 底层穿透
    location ~* /(api|ws)/ {
        proxy_pass http://$CONTAINER_NAME:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    # D. 主路由：全量交由 Next.js 管理 (包括 2FA 拦截与 /trading 等子页面)
    location / {
        proxy_pass http://$CONTAINER_NAME:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

if docker ps -a | grep -q $NGINX_CONTAINER; then
    docker rm -f $NGINX_CONTAINER
fi

docker run -d \
    --name $NGINX_CONTAINER \
    --restart always \
    -p $INSTALL_PORT:$INSTALL_PORT \
    --link $CONTAINER_NAME:$CONTAINER_NAME \
    -v $NGINX_DIR/default.conf:/etc/nginx/conf.d/default.conf:ro \
    nginx:alpine

# 7. 完成并展示
FINAL_URL="http://$SERVER_IP:$INSTALL_PORT$INSTALL_PATH/"

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}🎉 恭喜！套利引擎系统安装并在防护下运行成功。${NC}"
echo -e "请在浏览器中访问以下私密地址打开控制面："
echo -e "\n   ${YELLOW}▶️  $FINAL_URL ${NC}\n"

OTP_URI="otpauth://totp/?secret=${GOOGLE_AUTH_SECRET}&issuer=ArbitrageBot"
if command -v qrencode &> /dev/null; then
    log_info "【重要安全绑定】请使用 Google Authenticator 扫描下方二维码："
    qrencode -t ANSIUTF8 "${OTP_URI}"
else
    log_warn "【重要安全绑定】密钥：${RED}${GOOGLE_AUTH_SECRET}${NC}"
fi

echo -e "说明："
echo -e " 1. 2FA 密钥已保存在 $AUTH_FILE，重装不会失效。"
echo -e " 2. 系统将在后台自动工作，后续支持 UI 在线一键升级。"
echo -e "${GREEN}=====================================================${NC}"
