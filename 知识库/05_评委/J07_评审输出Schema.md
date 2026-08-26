---
card_id: J07
card_type: judge
roles:
- judge
verified: true
---

# 评审输出 Schema

```json
{
  "review_id": "REV-001",
  "stage": "G3",
  "artifact_versions": {},
  "decision": "REWORK",
  "blocking_issues": [{"id":"I-01","evidence":"...","impact":"..."}],
  "non_blocking_issues": [],
  "scores": {"model_validity":{"level":2,"evidence":"..."}},
  "actions": [{"owner":"engineer","task":"...","acceptance_test":"..."}],
  "invalidated_downstream_artifacts": [],
  "plan_patch": []
}
```

所有评分必须引用证据路径；没有证据时不能给3或4。自然语言建议放在结构化字段之后，不能替代Schema。
