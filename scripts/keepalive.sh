#!/bin/bash
# ---------------------------------------------------------------------------
# Streamlit-App-KeepAlive（下载自 https://github.com/ToroData/Streamlit-App-KeepAlive）
# 作用：交互式维护 .github/workflows/keep-streamlit-alive.yml，
#       由 GitHub Actions 定时访问 Streamlit 应用，避免云端休眠。
#
# 用法：bash scripts/keepalive.sh
# 说明：Windows 下推荐直接用 `python scripts/keepalive_app.py`（无需 Git Bash）；
#       本脚本已预置本项目的应用地址，初始化时会自动写入。
# ---------------------------------------------------------------------------

YAML_FILE=".github/workflows/keep-streamlit-alive.yml"
PROJECT_APP_URL="${STREAMLIT_APP_URL:-https://hdwqwu3howppf2z2xv9i2q.streamlit.app/}"
CRON_DEFAULT="0 */6 * * *"

# macOS 的 sed -i 需要额外空参数，这里做兼容
sed_inplace() {
    if sed --version >/dev/null 2>&1; then
        sed -i "$@"
    else
        sed -i '' "$@"
    fi
}

default_read() {
    local prompt="$1"
    local default="$2"
    local var
    read -p "$prompt [$default]: " var
    echo "${var:-$default}"
}

# 生成一次「访问应用」的 step（主页 + health 探针）
ping_step() {
    local url="$1"
    local name
    name=$(basename "$url")
    echo "      - name: Send request to $name"
    echo "        run: |"
    echo "          curl -s -o /dev/null -w \"home: %{http_code}\\n\" \"$url\""
    echo "          curl -s -o /dev/null -w \"health: %{http_code}\\n\" \"${url%/}/~/+/_stcore/health\""
}

initialize_yaml() {
    mkdir -p "$(dirname "$YAML_FILE")"
    cat > "$YAML_FILE" <<EOL
name: Keep Streamlit Apps Alive

on:
  schedule:
    - cron: '$CRON_DEFAULT'

  workflow_dispatch:

jobs:
  ping-apps:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
EOL
    ping_step "$PROJECT_APP_URL" >> "$YAML_FILE"
    echo "已初始化 $YAML_FILE 并写入: $PROJECT_APP_URL"
}

# 确保 YAML 存在且结构正确
if [ ! -f "$YAML_FILE" ] || [ ! -s "$YAML_FILE" ] || ! grep -q "name: Keep Streamlit Apps Alive" "$YAML_FILE"; then
    echo "YAML 文件缺失或损坏，重新初始化..."
    initialize_yaml
fi

CURRENT_NAME=$(grep -E '^name:' "$YAML_FILE" | head -n 1 | awk -F': ' '{print $2}')
CURRENT_CRON=$(grep -E 'cron: ' "$YAML_FILE" | head -n 1 | awk -F': ' '{print $2}' | tr -d "'")
NEW_NAME=$(default_read "Workflow name" "$CURRENT_NAME")
NEW_CRON=$(default_read "CRON expression for execution" "${CURRENT_CRON:-$CRON_DEFAULT}")

sed_inplace "s/^name:.*/name: $NEW_NAME/" "$YAML_FILE"
sed_inplace "s/cron: .*/cron: '$NEW_CRON'/" "$YAML_FILE"

add_app() {
    clear
    echo "Adding a new application..."
    read -p "Enter the URL of the new Streamlit app: " NEW_URL
    if [ -z "$NEW_URL" ]; then
        echo "URL 不能为空"
        sleep 2
        return
    fi
    ping_step "$NEW_URL" >> "$YAML_FILE"
    echo "Application added successfully!"
    sleep 2
}

while true; do
    clear
    echo "========== Streamlit App Manager =========="
    echo "1) Add a new application"
    echo "2) Exit"
    echo "==========================================="
    read -p "Select an option: " OPTION

    case $OPTION in
        1)
            add_app
            ;;
        2)
            clear
            exit 0
            ;;
        *)
            echo "Invalid option. Please try again."
            sleep 2
            ;;
    esac
done
