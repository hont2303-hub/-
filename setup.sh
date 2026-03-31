#!/bin/bash
# ============================================================
# note.com 自動投稿システム セットアップスクリプト（Mac用）
# 使い方: bash setup.sh
# ============================================================

set -e  # エラー時に停止

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "============================================"
echo "  note.com 自動投稿システム セットアップ"
echo "============================================"
echo ""

# ── STEP 1: Homebrew ──────────────────────────────────────
info "STEP 1/6: Homebrew を確認します..."
if ! command -v brew &>/dev/null; then
    info "Homebrew をインストールします（数分かかります）..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon Macの場合のパス設定
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
    success "Homebrew をインストールしました"
else
    success "Homebrew は既にインストール済みです"
fi

# ── STEP 2: Git / Python / Node.js ─────────────────────────
info "STEP 2/6: Git / Python 3.11 / Node.js をインストールします..."

if ! command -v git &>/dev/null; then
    brew install git
fi

if ! command -v python3.11 &>/dev/null && ! python3 --version 2>&1 | grep -q "3\.1[1-9]"; then
    brew install python@3.11
fi

if ! command -v node &>/dev/null; then
    brew install node
fi

# pythonコマンドを解決
if command -v python3.11 &>/dev/null; then
    PYTHON=python3.11
    PIP=pip3.11
elif python3 --version 2>&1 | grep -q "3\.1[1-9]"; then
    PYTHON=python3
    PIP=pip3
else
    error "Python 3.11以上が見つかりません。brew install python@3.11 を試してください。"
fi

success "Git: $(git --version)"
success "Python: $($PYTHON --version)"
success "Node: $(node --version)"

# ── STEP 3: リポジトリをクローン ───────────────────────────
INSTALL_DIR="$HOME/Desktop/note-automation"
info "STEP 3/6: リポジトリをクローンします → $INSTALL_DIR"

if [ -d "$INSTALL_DIR" ]; then
    warn "既に $INSTALL_DIR が存在します。スキップします。"
    cd "$INSTALL_DIR"
else
    git clone https://github.com/hont2303-hub/- "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

git checkout claude/note-automation-system-XoIgv 2>/dev/null || true
success "リポジトリのクローン完了: $INSTALL_DIR"

# ── STEP 4: .env ファイルを作成 ────────────────────────────
info "STEP 4/6: .env ファイルを作成します..."

if [ -f ".env" ]; then
    warn ".env は既に存在します。スキップします。"
else
    cp .env.example .env

    # 認証情報を入力してもらう
    echo ""
    echo "認証情報を入力してください（入力内容は画面に表示されません）"
    echo ""

    read -p "  Anthropic API Key: " ANTHROPIC_KEY
    read -p "  note.com メールアドレス: " NOTE_EMAIL_VAL
    read -s -p "  note.com パスワード: " NOTE_PASS_VAL; echo ""
    read -p "  X (Twitter) メールアドレス: " X_EMAIL_VAL
    read -s -p "  X (Twitter) パスワード: " X_PASS_VAL; echo ""
    read -p "  X (Twitter) ユーザー名(@なし): " X_USER_VAL
    read -p "  Google メールアドレス (Gemini用): " G_EMAIL_VAL
    read -s -p "  Google パスワード: " G_PASS_VAL; echo ""

    sed -i '' "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ANTHROPIC_KEY}|" .env
    sed -i '' "s|NOTE_EMAIL=.*|NOTE_EMAIL=${NOTE_EMAIL_VAL}|" .env
    sed -i '' "s|NOTE_PASSWORD=.*|NOTE_PASSWORD=${NOTE_PASS_VAL}|" .env
    sed -i '' "s|X_EMAIL=.*|X_EMAIL=${X_EMAIL_VAL}|" .env
    sed -i '' "s|X_PASSWORD=.*|X_PASSWORD=${X_PASS_VAL}|" .env
    sed -i '' "s|X_USERNAME=.*|X_USERNAME=${X_USER_VAL}|" .env
    sed -i '' "s|GOOGLE_EMAIL=.*|GOOGLE_EMAIL=${G_EMAIL_VAL}|" .env
    sed -i '' "s|GOOGLE_PASSWORD=.*|GOOGLE_PASSWORD=${G_PASS_VAL}|" .env

    success ".env を作成しました"
fi

# ── STEP 5: Pythonライブラリ & Playwright ─────────────────
info "STEP 5/6: Pythonライブラリをインストールします..."
$PIP install -e . --quiet
playwright install chromium
success "Pythonライブラリのインストール完了"

# ── STEP 6: Claude Code CLI ────────────────────────────────
info "STEP 6/6: Claude Code CLI をインストールします..."
if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
    success "Claude Code CLI をインストールしました"
else
    success "Claude Code CLI は既にインストール済みです: $(claude --version 2>/dev/null || echo '確認済み')"
fi

# ── 完了 ──────────────────────────────────────────────────
echo ""
echo "============================================"
echo -e "  ${GREEN}セットアップ完了！${NC}"
echo "============================================"
echo ""
echo "インストール先: $INSTALL_DIR"
echo ""
echo "次のステップ:"
echo ""
echo "  1. 記事を生成する:"
echo "     cd $INSTALL_DIR"
echo "     $PYTHON main.py --generate --export"
echo ""
echo "  2. Chrome で投稿する:"
echo "     claude --chrome"
echo "     → 「pending_posts.jsonの記事をnoteに投稿してください」と指示"
echo ""
echo "  3. 毎日自動生成（スケジューラ起動）:"
echo "     $PYTHON main.py --schedule"
echo ""
