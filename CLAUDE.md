# lxmusic 开发准则

## 发布流程 (Release Workflow)

每次 release 前必须：

1. 更新 `pyproject.toml` 中的 `version` 字段为待发布版本
2. 提交版本号变更：`git commit -m "chore: bump version to x.y.z"`
3. 创建并推送 tag：`git tag vx.y.z && git push origin vx.y.z`
4. 通过 `gh release create vx.y.z` 创建 GitHub Release

示例（发布 0.2.2）：

```bash
# 1. 修改 pyproject.toml: version = "0.2.2"
# 2. 提交
git add pyproject.toml && git commit -m "chore: bump version to 0.2.2"
# 3. 打 tag
git tag v0.2.2 && git push origin v0.2.2
# 4. 创建 release
gh release create v0.2.2 --title "v0.2.2" --notes "..."
```

Tag 必须指向包含版本号更新的 commit，否则 PyPI 发布的版本号会不匹配。
