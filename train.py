name: 大富豪 pick()係数最適化

on:
  workflow_dispatch:
    inputs:
      iter:
        description: '世代数'
        required: false
        default: '200'
      pop:
        description: 'population size'
        required: false
        default: '20'
      games:
        description: '評価ゲーム数'
        required: false
        default: '400'
      resume:
        description: '過去最良から再開 (true/false)'
        required: false
        default: 'false'

jobs:
  train:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install numpy

      - name: Run training
        run: |
          ARGS="--iter ${{ github.event.inputs.iter }} --pop ${{ github.event.inputs.pop }} --games ${{ github.event.inputs.games }}"
          if [ "${{ github.event.inputs.resume }}" = "true" ]; then
            ARGS="$ARGS --resume"
          fi
          python train.py $ARGS

      - name: Commit results
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add results.jsonl
          git diff --cached --quiet || git commit -m "chore: update training results [skip ci]"
          git push
