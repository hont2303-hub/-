# note.com 自動投稿システム

Claude Codeの活用記事をnote.comに自動投稿するシステムです。

## あなたの役割

このプロジェクトで `claude --chrome` を起動した場合、以下のワークフローを実行してください。

---

## ワークフロー全体

```
[Python側で事前実行]
python main.py --generate
  → Claude APIでトピック分析・記事生成
  → tasks/pending_posts.json に投稿タスクを出力

[あなた（Claude + Chrome）が実行]
1. tasks/pending_posts.json を読み込む
2. 各記事について以下を順番に実行:
   a. Gemini で図解画像を生成・保存
   b. note.com に記事を投稿
   c. X（Twitter）にツイートを投稿
   d. tasks/pending_posts.json のステータスを更新
```

---

## STEP 1: タスクファイルの確認

まず `tasks/pending_posts.json` を読み込んでください。

```
Read: tasks/pending_posts.json
```

`status: "pending"` の記事を処理対象にしてください。

---

## STEP 2: Gemini で画像生成

各記事について以下を実行してください：

1. Chrome で `https://gemini.google.com` を開く
2. 以下のプロンプトを送信：
   ```
   以下の記事タイトルに合う、シンプルでわかりやすい図解を作成してください：
   「{記事タイトル}」

   - 白背景
   - 日本語テキスト
   - 見やすいフローチャートまたは概念図
   ```
3. 生成された画像を `data/images/article_{id}_main.png` として保存
4. タスクファイルの `image_path` を更新

---

## STEP 3: note.com に記事を投稿

1. Chrome で `https://note.com/notes/new` を開く
2. **タイトル**を入力する
3. **本文**（body_markdown の内容）を貼り付ける
   - Markdownの見出し（##）はそのまま貼り付けてOK
   - note.comエディタが自動変換します
4. **画像**をアップロードする（Geminiで生成した画像）
5. **タグ**を設定する（hashtags の # を除いた文字列）
6. **「公開設定」→「投稿する」** をクリック
7. 投稿完了後のURLを記録する

---

## STEP 4: X（Twitter）にツイートを投稿

1. Chrome で `https://x.com` を開く
2. 新規ツイートボタンをクリック
3. 以下の形式でツイートを投稿：
   ```
   {summary の内容}

   {note記事URL}

   {hashtags をスペース区切りで}
   ```
4. 投稿完了を確認

---

## STEP 5: タスクステータスの更新

投稿完了後、`tasks/pending_posts.json` を更新してください：

```json
{
  "status": "posted",
  "note_url": "https://note.com/...",
  "posted_at": "2026-03-31 19:00:00"
}
```

また `shared/database.py` の `update_article_status()` を呼び出すか、
以下のPythonを実行してDBも更新してください：

```python
import sys
sys.path.insert(0, '.')
from shared.database import update_article_status
update_article_status(article_id={id}, status="posted", note_url="{url}")
```

---

## 注意事項

- **1記事ずつ確認しながら進めてください**（エラーがあれば教えてください）
- note.comのUIが変わっている場合は柔軟に対応してください
- Gemini、note.com、X はすべてChromeのログイン済みアカウントを使用します
- ログアウトされている場合は `hont2303@gmail.com` でログインしてください

---

## よく使うコマンド

```bash
# 記事を生成（ブラウザ不要）
python main.py --generate

# 投稿待ち記事を確認
python main.py --show-pending

# 1記事だけ生成テスト
python main.py --generate --count 1

# DBの状態を確認
python -c "from shared.database import *; init_db(); [print(a.title, a.status) for a in get_ready_articles(10)]"
```
