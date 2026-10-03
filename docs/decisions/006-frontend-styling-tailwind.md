# ADR-006: 前端样式体系引入 Tailwind CSS

## 状态

Accepted

## 背景

前端此前仅有各页面 `<style scoped>` 与 Element Plus 自带样式，存在以下问题：

- 全局样式 `src/style.css` 为 Vite 脚手架残留（`#app` 固定 1126px、`prefers-color-scheme` 媒体查询等），污染后台布局。
- 布局、间距、响应式与色值分散在行内样式与 scoped 样式中，硬编码色值（`#409eff`、`#909399` 等）与 Element Plus 主题脱节。
- 布局无响应式与折叠能力，暗色主题缺失。

需要引入一套样式方案，在不替换 Element Plus 组件库的前提下，统一布局、间距、响应式与主题能力。

## 决策

引入 **Tailwind CSS v4**，通过 `@tailwindcss/vite` 插件接入，采用 CSS-first 配置：

- Tailwind 负责布局、间距、响应式与主题 token；Element Plus 继续负责表单/表格/弹窗/消息等成品组件。
- 唯一样式入口 `src/style.css` 声明层序：`theme < base < element-plus < components < utilities`。
  - Element Plus 的 CSS 未使用 `@layer`，默认会压过 Tailwind utilities；显式 `@import 'element-plus/dist/index.css' layer(element-plus)` 将其归层。
  - `element-plus` 置于 `base`（Preflight）之后、`utilities` 之前：避免 Preflight 重置破坏 EP 组件样式，同时保证 Tailwind 工具类可覆盖 EP。
- 品牌色以 `@theme` 定义色阶（`brand-50`…`brand-900`），语义色直接复用 Element Plus CSS 变量（`var(--el-color-*)`），保证与组件库一致。
- 暗色主题使用 Element Plus dark css-vars + `html.dark`，由 `store/theme.js` 持久化到 localStorage，支持浅色/深色/跟随系统。

## 备选方案

### 纯 scoped CSS + CSS 变量

- 优点：无新依赖。
- 缺点：布局/响应式需手写，样板多，难以统一。

### UnoCSS

- 优点：原子化、可定制、体积小。
- 缺点：生态与团队认知度低于 Tailwind，配置心智成本相近。

### 引入 UI 框架替换 Element Plus

- 优点：视觉统一。
- 缺点：改动面极大，风险与成本远超本次优化目标。

## 影响

### 正面

- 布局与响应式以工具类表达，样板代码显著减少。
- 主题 token 集中，色值与 Element Plus 变量对齐，暗色主题低成本接入。
- 与 Vite 8 兼容（`@tailwindcss/vite@4.3` peer 支持 Vite 8），无需 PostCSS 额外配置。

### 负面

- 新增构建依赖，`package-lock.json` 变动，`npm ci` 与 Docker 构建需同步。
- 依赖层序的隐式约定：Element Plus 升级若改变 CSS 分层策略，需重新核对。
- Preflight 与 EP 基础样式存在潜在冲突，需视觉回归。
