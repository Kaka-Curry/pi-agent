# TRAIN-ML-PIPELINE-P0-20261101

- **time**: 2026-11-01 Asia/Shanghai
- **face**: 研究闭环/Codex
- **约束**: 不改 scoring_config / 外层权重；不写 PRIMARY；不下单；不覆盖 shap 生产模型；`approved` 保持 false；生产分保持 v3.7

## 本刀实际完成

纸面闸门不再把 `pick5d_ml` 写死为空。

- 落盘 `control_plane/state/paper_ab_ml_arms_void.json`。
- `research_loop/paper_gate.py` 读取其中 `clean_window`。窗口固定 20 日；只有尾部 20 日全部干净且带有 `pick5d_ml` 时，闸门才给出该 pick，并把 `promote` 标为纸面窗通过。
- 当前文件 `days` 为空（样本不足 20 日，与试跑结论一致）。默认评估结果是 `promote=false`、`reason=insufficient_clean_window`，不是硬编码的恒 None。
- 决策里的 `approved` 固定 false，`production_score` 固定 `v3.7`。文件里即使写成别的值也不被采纳。

## 本刀未做（主控改优先级，不阻塞）

- retrain 日志 `trigger` 字段
- 看板并列生产 WF IC 与 lens OOS IC
- 归档过期 `sweep_horizon_b_results.json`

## 验证

```bash
python3 -m pytest tests/test_paper_gate.py
```

## 签字

研究闭环/Codex
