# score_trim

楽譜PDFを右に90度回転し、奇数/偶数ページで異なるプリセット枠でトリミングする。

## 使い方

相対・絶対パスどちらも可。複数指定・混在可。

```sh
# フォルダ (サブフォルダ内のPDFも対象)
cd ~/Documents/Python/GM9
uv run score_trim.py raw

# ファイル1つ
cd ~/Documents/Python/GM9
uv run score_trim.py raw/マラ9管打楽譜/Mahler9_Fl.pdf

# 複数ファイル (絶対パス)
cd ~/Documents/Python/GM9
uv run score_trim.py ~/Downloads/a.pdf ~/Downloads/b.pdf

# フォルダとファイルの混在
cd ~/Documents/Python/GM9
uv run score_trim.py raw/マラ9管打楽譜 extra.pdf

# 引数なし: フォルダ選択ダイアログ
cd ~/Documents/Python/GM9
uv run score_trim.py
```

## 出力

- フォルダ指定 → `out/<フォルダからの相対パス>`
- ファイル指定 → `out/<ファイル名>`
- 元ファイルは変更しない

## 操作

| キー・操作 | 動作 |
|---|---|
| ← / → | ページ移動 (端で前後のファイルへ) |
| n / p | 次 / 前のファイル |
| t | このファイルの回転を切替 (右90度 / なし) |
| 1 / 2 / 3 | このページにプリセットを適用 |
| ドラッグ | 枠を移動 |
| 右ドラッグ | 枠を描き直す (A4比率のまま、縦のドラッグ量で大きさを決める) |
| ホイール | プレビューの拡大縮小 (はみ出たらスクロールバー) |
| 右スライダー | 枠サイズ (A4比率のまま) |
| a | このページの枠を同じ奇偶の全ページへコピー |
| r | このページを既定 (奇数=A, 偶数=B) に戻す |
| s | このファイルを保存して次のファイルへ |

## 画質

回転は `/Rotate`、トリミングは CropBox の書き換えのみ。中身は再エンコードしない。
