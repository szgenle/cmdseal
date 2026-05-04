# 双平台推送配置说明

本项目同时向两个代码托管平台推送代码：

## Remote 配置

```bash
# 查看当前 remote 配置
git remote -v

# 输出应为：
# github  git@github.com:szgenle/cmdseal.git (fetch)
# github  git@github.com:szgenle/cmdseal.git (push)
# origin  git@codeup.aliyun.com:686b30d78856a83b0134f4f1/cmdseal/cmdseal.git (fetch)
# origin  git@codeup.aliyun.com:686b30d78856a83b0134f4f1/cmdseal/cmdseal.git (push)
```

## 推送方式

### 方式一：使用本地脚本（推荐）

```bash
# 项目根目录下执行
./sync-to-github.sh
```

> **注意：** `sync-to-github.sh` 是本地脚本，已加入 `.gitignore`，不会提交到仓库。

### 方式二：手动推送

```bash
# 推送到阿里云 CodeUp
git push origin main

# 推送到 GitHub
git push github main
```

## 平台地址

- **阿里云 CodeUp**（主仓库）: https://codeup.aliyun.com/szgenle/cmdseal
- **GitHub**（镜像仓库）: https://github.com/szgenle/cmdseal

## 首次推送

如果 GitHub 仓库是空的，首次推送使用：

```bash
git push -u github main
```

这会建立跟踪关系，之后可以直接 `git push github main`。

## 分支策略

- `main` 分支：稳定版本，推送到两个平台
- 功能分支：可以在本地开发，不需要推送到两个平台

## 注意事项

1. 确保两个平台的 SSH key 都已配置
2. GitHub 使用 `git@github.com:szgenle/cmdseal.git`
3. CodeUp 使用 `git@codeup.aliyun.com:...`
4. 推送顺序：先 `origin`（CodeUp），后 `github`
