# 大富豪 勝率シミュレータ

モンテカルロ法 + スコアモードの2モード対応。  
**`index.html` 1ファイルのみ** — サーバー不要、ブラウザだけで動作します。

## 🚀 GitHub Pages デプロイ

```bash
git init
git add index.html README.md
git commit -m "feat: 大富豪勝率シミュレータ"
git remote add origin https://github.com/<yourname>/daifugo-analyzer.git
git push -u origin main
```

GitHubリポジトリの **Settings → Pages → Branch: main / root → Save**  
→ `https://<yourname>.github.io/daifugo-analyzer/` で公開完了

ローカルでは `index.html` をダブルクリックするだけで動きます。

## 計算モード

| モード | 速度 | 特徴 |
|---|---|---|
| **スコアモード** | 即時 | カード強度・組み手・革命価値を数式で評価 |
| **モンテカルロ** | 数秒 | 仮想対戦を繰り返して統計的に算出（200〜1000回） |

## 採用ルール

- 人数: 3〜5人（デフォルト3人）
- 8切り: ON/OFF切替可
- ジョーカー: 2枚（スペード3返しなし・常に最強）
- 革命: 4枚同数字出しで成立、革命中は強弱逆転
- 革命返し: より弱い数字の4枚組で返せる
- 階段・縛り: なし
