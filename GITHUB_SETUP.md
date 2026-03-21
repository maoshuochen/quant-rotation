# GitHub 仓库部署指南

由于当前环境的 GitHub 权限限制，需要手动在 GitHub 上创建仓库并推送代码。

---

## 步骤 1: 在 GitHub 上创建仓库

### 1.1 访问 GitHub
打开浏览器访问：https://github.com/new

### 1.2 填写仓库信息
- **Repository name**: `quant-rotation`
- **Description**: `指数轮动量化系统 - 基于多因子评分的 A 股指数轮动策略`
- **Public**: ✅ 选择公开仓库
- **Initialize this repository with**: ❌ 不要勾选（保持空仓库）

### 1.3 点击 "Create repository"

---

## 步骤 2: 配置 SSH 密钥（如未配置）

### 2.1 生成 SSH 密钥
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# 按回车使用默认路径
```

### 2.2 查看公钥
```bash
cat ~/.ssh/id_ed25519.pub
```

### 2.3 添加到 GitHub
1. 访问：https://github.com/settings/keys
2. 点击 "New SSH key"
3. 粘贴公钥内容
4. 点击 "Add SSH key"

### 2.4 测试连接
```bash
ssh -T git@github.com
# 应该显示：Hi maoshuochen! You've successfully authenticated
```

---

## 步骤 3: 推送代码到 GitHub

### 3.1 添加远程仓库
```bash
cd /root/.openclaw/workspace/quant-rotation
git remote add origin git@github.com:maoshuochen/quant-rotation.git
```

### 3.2 推送代码
```bash
git push -u origin main
```

### 3.3 验证推送
访问：https://github.com/maoshuochen/quant-rotation
应该能看到所有代码文件。

---

## 步骤 4: 配置 GitHub Pages（可选）

### 4.1 启用 GitHub Pages
1. 访问仓库 Settings → Pages
2. Source: 选择 `GitHub Actions`
3. 保存

### 4.2 创建 GitHub Actions 工作流

创建 `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: web/package-lock.json
      
      - name: Install dependencies
        run: |
          cd web
          npm ci
      
      - name: Build
        run: |
          cd web
          npm run build
      
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./web/dist

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### 4.3 访问部署的页面
```
https://maoshuochen.github.io/quant-rotation/
```

---

## 步骤 5: 更新 README 中的链接

编辑 `README.md`，将链接更新为你的 GitHub 仓库：

```markdown
- 项目 Issue: https://github.com/maoshuochen/quant-rotation/issues
- 作者 GitHub: https://github.com/maoshuochen
```

---

## 快速命令参考

```bash
# 查看远程仓库
git remote -v

# 修改远程仓库 URL
git remote set-url origin git@github.com:maoshuochen/quant-rotation.git

# 推送代码
git push -u origin main

# 拉取代码
git pull origin main

# 查看状态
git status

# 查看日志
git log --oneline
```

---

## 常见问题

### Q1: Permission denied (publickey)
**解决**: 
1. 确保已生成 SSH 密钥
2. 将公钥添加到 GitHub
3. 测试连接：`ssh -T git@github.com`

### Q2: fatal: remote origin already exists
**解决**:
```bash
git remote remove origin
git remote add origin git@github.com:maoshuochen/quant-rotation.git
```

### Q3: 推送后看不到文件
**解决**:
1. 刷新 GitHub 页面
2. 检查是否推送到正确的分支：`git branch`
3. 重新推送：`git push -u origin main`

---

## 后续维护

### 提交新更改
```bash
git add .
git commit -m "描述更改内容"
git push
```

### 拉取他人更改
```bash
git pull origin main
```

### 创建新版本
```bash
git tag v0.2.0
git push origin v0.2.0
```

---

## 仓库地址

- **HTTPS**: `https://github.com/maoshuochen/quant-rotation.git`
- **SSH**: `git@github.com:maoshuochen/quant-rotation.git`

---

*文档更新时间：2026-03-21*
