<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import { connect, disconnect, on, off } from '../utils/ws'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

const router = useRouter()
const route = useRoute()
const app = useAppStore()
const auth = useAuthStore()
const themeStore = useThemeStore()

const logoSrc = '/web/favicon.svg'
const wsConnected = ref(false)
const mobileMenuOpen = ref(false)
const isMobile = ref(false)
const restarting = ref(false)
const showDefaultPwdWarning = ref(false)

const NAV_ITEMS = [
  { label: '仪表盘', key: 'Dashboard', icon: 'home' },
  { label: '全局日志', key: 'Logs', icon: 'document-text' },
  { label: '插件模块', key: 'Plugins', icon: 'extension-puzzle' },
  { label: '数据库', key: 'Database', icon: 'server' },
  { label: '消息记录', key: 'Messages', icon: 'chatbubbles' },
  { label: '可视统计', key: 'Statistics', icon: 'stats-chart' },
  { label: '插件市场', key: 'Market', icon: 'storefront' },
  { label: '网络配置', key: 'Network', icon: 'link' },
  { label: '框架配置', key: 'Config', icon: 'settings' },
  { label: '框架更新', key: 'Update', icon: 'cloud-download' },
]

const currentRouteName = computed(() => route.name)
const botOptions = computed(() => [
  ...(app.bots.length > 1 ? [{ label: '全部机器人', value: '' }] : []),
  ...app.bots.map(b => ({ label: b.name || b.bot_qq, value: b.bot_qq })),
])

// Bot detail modal
const showBotDetail = ref(false)
const detailBot = ref(null)
const togglingBot = ref('')

async function handleToggleBot(bot, enabled) {
  togglingBot.value = bot.bot_qq
  const ok = await app.toggleBot(bot.bot_qq, enabled)
  togglingBot.value = ''
  if (ok) {
    window.$message?.success(enabled ? '机器人已启用' : '机器人已关闭')
  } else {
    window.$message?.error('操作失败')
  }
}

function navigate(name) {
  router.push({ name })
  mobileMenuOpen.value = false
}

function navigateCustom(key) {
  router.push({ name: 'CustomPage', params: { key } })
  mobileMenuOpen.value = false
}

async function handleRestart() {
  restarting.value = true
  try {
    await axios.post('/api/bot/restart')
    window.$message?.success('重启指令已发送，请等待服务恢复...') || alert('重启指令已发送')
  } catch {
    window.$message?.error('重启失败') || alert('重启失败')
  } finally {
    restarting.value = false
  }
}

function handleResize() { isMobile.value = window.innerWidth < 768 }
function onWsOpen() { wsConnected.value = true }
function onWsClose() { wsConnected.value = false }

function fetchBotDetail(bot) {
  detailBot.value = bot
  showBotDetail.value = true
}

function goConfig() { router.push({ name: 'Config' }) }

async function checkDefaultPassword() {
  // 以后端实际配置为准, 避免本地缓存的弱密码标记导致"默认密码"误报
  try {
    const res = await axios.get('/api/auth/password-status')
    const weak = !!(res.data?.is_default || res.data?.is_weak)
    showDefaultPwdWarning.value = weak
    if (!weak) localStorage.removeItem('elaina_weak_pwd')
    return
  } catch {}
  // 接口异常时回退到本地标记
  if (auth.isWeakPassword) showDefaultPwdWarning.value = true
}

async function clearCache() {
  try {
    if ('caches' in window) {
      const keys = await caches.keys()
      await Promise.all(keys.map(k => caches.delete(k)))
    }
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      await Promise.all(regs.map(r => r.unregister()))
    }
    localStorage.clear()
    sessionStorage.clear()
    // 强制绕过浏览器 HTTP 缓存重新加载
    window.location.href = window.location.pathname + '?_t=' + Date.now()
  } catch { window.location.href = window.location.pathname + '?_t=' + Date.now() }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  handleResize()
  window.addEventListener('resize', handleResize)
  await app.ensureBots()
  app.fetchSystemInfo()
  await app.fetchWebPages()
  connect()
  on('open', onWsOpen)
  on('close', onWsClose)
  checkDefaultPassword()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  off('open', onWsOpen)
  off('close', onWsClose)
  disconnect()
})
</script>

<template>
  <div class="layout-root">
    <!-- Mobile overlay -->
    <div v-if="mobileMenuOpen" class="mobile-overlay" @click="mobileMenuOpen = false" />

    <!-- Sidebar -->
    <aside :class="['sidebar', { open: mobileMenuOpen, collapsed: app.sidebarCollapsed && !isMobile }]">
      <div class="sidebar-logo">
        <img class="logo-icon" :src="logoSrc" alt="Elaina" />
        <span v-if="!app.sidebarCollapsed || isMobile">Elaina</span>
      </div>

      <div v-if="(!app.sidebarCollapsed || isMobile) && app.bots.length > 1" class="sidebar-bot-select">
        <n-select v-model:value="app.currentBotId" :options="botOptions" size="small"
          placeholder="全部机器人" @update:value="app.switchBot" />
      </div>

      <nav class="sidebar-nav">
        <a v-for="item in NAV_ITEMS" :key="item.key"
          :class="['nav-item', { active: currentRouteName === item.key }]"
          @click="navigate(item.key)">
          <SvgIcon :name="item.icon" :size="18" />
          <span v-if="!app.sidebarCollapsed || isMobile">{{ item.label }}</span>
        </a>

        <template v-if="app.webPages.length">
          <div v-if="!app.sidebarCollapsed || isMobile" class="nav-divider">扩展页面</div>
          <a v-for="page in app.webPages" :key="page.key"
            :class="['nav-item', { active: route.params.key === page.key && route.name === 'CustomPage' }]"
            @click="navigateCustom(page.key)">
            <SvgIcon name="extension-puzzle" :size="18" />
            <span v-if="!app.sidebarCollapsed || isMobile" class="nav-label-with-badge">
              {{ page.label }}
              <SvgIcon :name="page.source === 'module' ? 'cube' : 'link'" :size="12" class="nav-badge" />
            </span>
          </a>
        </template>
      </nav>

      <div v-if="!isMobile" class="sidebar-toggle" @click="app.sidebarCollapsed = !app.sidebarCollapsed">
        <SvgIcon :name="app.sidebarCollapsed ? 'chevron-forward' : 'chevron-back'" :size="16" />
      </div>
    </aside>

    <!-- Main area -->
    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <button v-if="isMobile" class="hamburger" @click="mobileMenuOpen = !mobileMenuOpen">
            <SvgIcon name="menu" :size="22" />
          </button>

          <!-- Multi-bot selector -->
          <n-popover v-if="app.bots.length > 1" trigger="click" placement="bottom-start">
            <template #trigger>
              <div class="bot-selector">
                <template v-if="app.isAllBots">
                  <span class="ws-dot online" />
                  <span class="bot-name">全部机器人</span>
                  <span class="bot-qq">{{ app.bots.length }} 个</span>
                </template>
                <template v-else>
                  <img v-if="app.currentBot?.avatar" :src="app.currentBot.avatar" class="bot-avatar-tiny" />
                  <span v-else class="bot-avatar-letter">{{ (app.currentBot?.name || '?').charAt(0) }}</span>
                  <span :class="['ws-dot', app.currentBot?.connected ? 'online' : app.currentBot?.connection_type === 'Webhook' ? 'waiting' : 'offline']" />
                  <span class="bot-name">{{ app.currentBot?.name || '未知' }}</span>
                  <n-tag :bordered="false" size="tiny" :type="app.currentBot?.connection_type === 'Webhook' ? 'info' : 'success'" style="font-size:10px">
                    {{ app.currentBot?.connection_type === 'Webhook' ? 'WH' : 'WS' }}
                  </n-tag>
                </template>
                <SvgIcon name="chevron-forward" :size="14" style="transform:rotate(90deg);opacity:0.5" />
              </div>
            </template>
            <div class="bot-switch-list">
              <div :class="['bot-switch-item', { active: app.isAllBots }]" @click="app.switchBot('')">
                <span class="ws-dot online" />
                <span class="bot-name">全部机器人</span>
                <span class="bot-qq">{{ app.bots.length }} 个</span>
              </div>
              <div v-for="bot in app.bots" :key="bot.bot_qq"
                :class="['bot-switch-item', { active: bot.bot_qq === app.currentBotId, disabled: bot.enabled === false }]"
                @click="bot.enabled !== false && app.switchBot(bot.bot_qq)">
                <img v-if="bot.avatar" :src="bot.avatar" class="bot-avatar-tiny" :style="bot.enabled === false ? 'opacity:0.4' : ''" />
                <span v-else class="bot-avatar-letter" :style="bot.enabled === false ? 'opacity:0.4' : ''">{{ (bot.name || bot.bot_qq).charAt(0) }}</span>
                <span v-if="bot.enabled !== false" :class="['ws-dot', bot.connected ? 'online' : bot.connection_type === 'Webhook' ? 'waiting' : 'offline']" />
                <span v-else class="ws-dot offline" />
                <span class="bot-info-col">
                  <span class="bot-name" :style="bot.enabled === false ? 'opacity:0.5' : ''">{{ bot.name || bot.bot_qq }}</span>
                  <span class="bot-qq">{{ bot.bot_qq }}</span>
                </span>
                <n-tag v-if="bot.enabled !== false" :bordered="false" size="tiny" :type="bot.connection_type === 'Webhook' ? 'info' : 'success'" style="font-size:10px;flex-shrink:0">
                  {{ bot.connection_type === 'Webhook' ? 'WH' : 'WS' }}
                </n-tag>
                <n-tag v-else :bordered="false" size="tiny" type="warning" style="font-size:10px;flex-shrink:0">已关闭</n-tag>
                <n-switch size="small" :value="bot.enabled !== false" :loading="togglingBot === bot.bot_qq"
                  @click.stop @update:value="v => handleToggleBot(bot, v)" />
                <n-button quaternary circle size="tiny" @click.stop="fetchBotDetail(bot)" title="详情" style="flex-shrink:0">
                  <template #icon><SvgIcon name="information-circle" :size="14" /></template>
                </n-button>
              </div>
            </div>
          </n-popover>

          <!-- Single bot display -->
          <div v-else-if="app.bots.length === 1" class="bot-selector">
            <template v-if="app.bots[0].enabled !== false">
              <img v-if="app.bots[0].avatar" :src="app.bots[0].avatar" class="bot-avatar-tiny" />
              <span v-else class="bot-avatar-letter">{{ (app.bots[0].name || '?').charAt(0) }}</span>
              <span :class="['ws-dot', app.bots[0].connected ? 'online' : app.bots[0].connection_type === 'Webhook' ? 'waiting' : 'offline']" />
              <span class="bot-name">{{ app.bots[0].name || '未知' }}</span>
              <n-tag :bordered="false" size="tiny" :type="app.bots[0].connection_type === 'Webhook' ? 'info' : 'success'" style="font-size:10px">
                {{ app.bots[0].connection_type === 'Webhook' ? 'WH' : 'WS' }}
              </n-tag>
            </template>
            <template v-else>
              <span class="bot-avatar-letter" style="opacity:0.4">{{ (app.bots[0].name || '?').charAt(0) }}</span>
              <span class="ws-dot offline" />
              <span class="bot-name" style="opacity:0.5">{{ app.bots[0].name || '未知' }}</span>
              <n-tag :bordered="false" size="tiny" type="warning" style="font-size:10px">已关闭</n-tag>
            </template>
            <n-switch size="small" :value="app.bots[0].enabled !== false" :loading="togglingBot === app.bots[0].bot_qq"
              @update:value="v => handleToggleBot(app.bots[0], v)" style="margin-left:4px" />
            <n-button quaternary circle size="tiny" @click="fetchBotDetail(app.bots[0])" title="详情">
              <template #icon><SvgIcon name="information-circle" :size="14" /></template>
            </n-button>
          </div>

          <span :class="['ws-dot ws-main', wsConnected ? 'online' : 'offline']" title="WebSocket" />
        </div>

        <div class="topbar-right">
          <!-- GitHub -->
          <a href="https://github.com/ElainaCore/ElainaBot-Onebot" target="_blank" rel="noopener"
            title="GitHub" class="github-link">
            <SvgIcon name="github" :size="18" />
          </a>

          <!-- Theme picker -->
          <n-popover trigger="click" placement="bottom-end">
            <template #trigger>
              <n-button quaternary circle size="small" title="主题">
                <template #icon><SvgIcon name="color-palette" :size="18" /></template>
              </n-button>
            </template>
            <div class="theme-picker">
              <div v-for="(t, key) in themeStore.THEMES" :key="key"
                :class="['theme-opt', { active: themeStore.themeName === key }]"
                @click="themeStore.setTheme(key)">
                <span class="theme-dot" :style="{ background: t.accent }" />
                {{ t.name }}
              </div>
            </div>
          </n-popover>

          <!-- Clear Cache -->
          <n-button quaternary circle size="small" title="清除缓存" @click="clearCache">
            <template #icon><SvgIcon name="trash" :size="18" /></template>
          </n-button>

          <!-- Restart -->
          <n-popconfirm @positive-click="handleRestart" positive-text="确认重启" negative-text="取消">
            <template #trigger>
              <n-button quaternary circle size="small" :loading="restarting">
                <template #icon><SvgIcon name="refresh" :size="18" /></template>
              </n-button>
            </template>
            确定要重启机器人吗？重启期间服务将暂时不可用。
          </n-popconfirm>

          <!-- Logout -->
          <n-button quaternary circle size="small" @click="handleLogout">
            <template #icon><SvgIcon name="log-out" :size="18" /></template>
          </n-button>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- Default password warning modal -->
    <n-modal v-model:show="showDefaultPwdWarning" preset="dialog" type="warning"
      title="安全提醒" positive-text="前往修改" @positive-click="goConfig" closable mask-closable>
      检测到当前 Web 面板使用的是默认密码，存在安全风险，请尽快修改。
    </n-modal>

    <!-- Bot detail modal -->
    <n-modal v-model:show="showBotDetail" preset="card" title="机器人详情"
      :style="{ width: isMobile ? '95vw' : '600px', maxWidth: '600px', background: 'var(--bg2)' }">
      <div v-if="detailBot" class="bot-detail">
        <div class="bd-header">
          <n-avatar v-if="detailBot.avatar" :src="detailBot.avatar" :size="72" round />
          <div v-else class="bd-avatar-placeholder">{{ (detailBot.name || detailBot.bot_qq).charAt(0) }}</div>
          <div class="bd-header-info">
            <div class="bd-name">{{ detailBot.name || '未知机器人' }}</div>
            <div class="bd-sub">QQ: {{ detailBot.qq || detailBot.bot_qq }}</div>
            <div class="bd-sub">OneBot v11 协议机器人</div>
          </div>
        </div>

        <n-descriptions :column="2" label-placement="left" size="small" class="bd-info">
          <n-descriptions-item label="机器人开关">
            <n-switch size="small" :value="detailBot.enabled !== false" :loading="togglingBot === detailBot.bot_qq"
              @update:value="v => handleToggleBot(detailBot, v)" />
          </n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="detailBot.connected ? 'success' : 'error'" size="small">
              {{ detailBot.connected ? '已连接' : '未连接' }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="连接方式">{{ detailBot.connection_type || 'WebSocket' }}</n-descriptions-item>
        </n-descriptions>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.layout-root {
  display:flex;
  height:100vh;
  overflow:hidden;
  background:var(--bg)
}
.sidebar {
  width:220px;
  flex-shrink:0;
  background:var(--bg2);
  display:flex;
  flex-direction:column;
  border-right:1px solid var(--border);
  box-shadow:1px 0 0 var(--border);
  transition:width .2s,transform .25s;
  z-index:100
}
.sidebar.collapsed {
  width:64px
}
.sidebar.collapsed .logo-text,.sidebar.collapsed .sidebar-bot-select,.sidebar.collapsed .nav-item span {
  display:none
}
.sidebar.collapsed .nav-item {
  justify-content:center;
  padding:12px 0
}
.sidebar-logo {
  display:flex;
  align-items:center;
  gap:10px;
  padding:16px;
  border-bottom:1px solid var(--border)
}
.logo-icon {
  width:32px;
  height:32px;
  border-radius:8px;
  flex-shrink:0;
  -o-object-fit:contain;
  object-fit:contain
}
.logo-text {
  color:var(--text);
  font-weight:600;
  font-size:16px;
  white-space:nowrap
}
.sidebar-bot-select {
  padding:8px 12px
}
.sidebar-nav {
  flex:1;
  overflow-y:auto;
  padding:8px 0
}
.nav-item {
  display:flex;
  align-items:center;
  gap:11px;
  padding:10px 14px;
  margin:3px 10px;
  border-radius:10px;
  color:var(--text2);
  cursor:pointer;
  transition:all .15s;
  text-decoration:none;
  font-size:14px;
  font-weight:500;
  position:relative
}
.nav-item:hover {
  background:var(--bg3);
  color:var(--text)
}
.nav-item.active {
  background:var(--accent-soft);
  color:var(--accent);
  font-weight:600
}
.nav-item.active::before {
  content:"";
  position:absolute;
  left:-10px;
  top:50%;
  transform:translateY(-50%);
  width:3px;
  height:18px;
  border-radius:0 3px 3px 0;
  background:var(--accent)
}
.nav-divider {
  font-size:11px;
  color:var(--text3);
  padding:12px 16px 4px;
  text-transform:uppercase;
  letter-spacing:.5px;
  font-weight:600
}
.nav-label-with-badge {
  display:inline-flex;
  align-items:center;
  gap:4px
}
.nav-badge {
  opacity:.5;
  flex-shrink:0
}
.sidebar-toggle {
  padding:12px;
  text-align:center;
  border-top:1px solid var(--border);
  cursor:pointer;
  color:var(--text3)
}
.sidebar-toggle:hover {
  color:var(--text)
}
.main-area {
  flex:1;
  display:flex;
  flex-direction:column;
  overflow:hidden;
  min-width:0
}
.topbar {
  height:52px;
  flex-shrink:0;
  padding:0 16px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  background:var(--bg2);
  border-bottom:1px solid var(--border)
}
.topbar-left {
  display:flex;
  align-items:center;
  gap:8px
}
.bot-selector {
  display:flex;
  align-items:center;
  gap:6px;
  padding:4px 10px;
  border-radius:6px;
  cursor:pointer;
  transition:background .15s
}
.bot-selector:hover {
  background:var(--border)
}
.bot-avatar-tiny {
  width:22px;
  height:22px;
  border-radius:50%;
  -o-object-fit:cover;
  object-fit:cover;
  flex-shrink:0
}
.bot-avatar-letter {
  width:22px;
  height:22px;
  border-radius:50%;
  flex-shrink:0;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:11px;
  font-weight:700;
  color:#fff;
  background:linear-gradient(135deg,#5865f2,#7289da)
}
.bot-name {
  color:var(--text);
  font-size:14px;
  font-weight:600
}
.bot-qq {
  color:var(--text3);
  font-size:12px;
  font-family:monospace
}
.bot-info-col {
  display:flex;
  flex-direction:column;
  flex:1;
  min-width:0
}
.bot-info-col .bot-name {
  font-size:13px;
  line-height:1.2;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis
}
.bot-info-col .bot-qq {
  font-size:11px;
  line-height:1.2
}
.bot-switch-list {
  display:flex;
  flex-direction:column;
  gap:2px;
  min-width:260px
}
.bot-switch-item {
  display:flex;
  align-items:center;
  gap:6px;
  padding:6px 10px;
  border-radius:6px;
  cursor:pointer;
  font-size:13px
}
.bot-switch-item:hover {
  background:var(--border)
}
.bot-switch-item.active {
  background:var(--accent)
}
.bot-switch-item.active .bot-name {
  color:#fff
}
.bot-switch-item.active .bot-qq {
  color:#fff9
}
.ws-main {
  margin-left:2px
}
.topbar-right {
  display:flex;
  align-items:center;
  gap:4px
}
.github-link {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:28px;
  height:28px;
  border-radius:50%;
  color:var(--text2);
  transition:color .15s;
  text-decoration:none
}
.github-link:hover {
  color:var(--text)
}
.hamburger {
  background:none;
  border:none;
  color:var(--text2);
  cursor:pointer;
  padding:4px;
  display:flex;
  align-items:center
}
.ws-dot {
  width:8px;
  height:8px;
  border-radius:50%
}
.ws-dot.online {
  background:var(--success);
  box-shadow:0 0 6px var(--success)
}
.ws-dot.waiting {
  background:var(--info);
  box-shadow:0 0 6px var(--info)
}
.ws-dot.offline {
  background:var(--text3)
}
.content {
  flex:1;
  overflow-y:auto;
  padding:20px;
  padding-bottom:calc(20px + env(safe-area-inset-bottom, 0px))
}
.page-enter-active,.page-leave-active {
  transition:opacity .15s
}
.page-enter-from,.page-leave-to {
  opacity:0
}
.mobile-overlay {
  position:fixed;
  top:0;
  right:0;
  bottom:0;
  left:0;
  background:#00000080;
  z-index:99
}
.theme-picker {
  display:flex;
  flex-direction:column;
  gap:4px;
  min-width:120px
}
.theme-opt {
  display:flex;
  align-items:center;
  gap:8px;
  padding:6px 10px;
  border-radius:6px;
  cursor:pointer;
  color:var(--text2);
  font-size:13px
}
.theme-opt:hover {
  background:var(--border);
  color:var(--text)
}
.theme-opt.active {
  color:var(--accent);
  font-weight:600
}
.theme-dot {
  width:12px;
  height:12px;
  border-radius:50%;
  flex-shrink:0
}
.bot-detail {
  display:flex;
  flex-direction:column;
  gap:16px
}
.bd-header {
  display:flex;
  align-items:center;
  gap:16px
}
.bd-avatar-placeholder {
  width:72px;
  height:72px;
  border-radius:50%;
  flex-shrink:0;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:28px;
  font-weight:700;
  color:#fff;
  background:linear-gradient(135deg,#5865f2,#7289da)
}
.bd-header-info {
  flex:1;
  min-width:0
}
.bd-name {
  font-size:18px;
  font-weight:700;
  color:var(--text)
}
.bd-sub {
  font-size:12px;
  color:var(--text2);
  margin-top:2px
}
.bd-desc {
  padding:10px 14px;
  border-radius:8px;
  font-size:13px;
  color:var(--text2);
  background:var(--bg3);
  line-height:1.6
}
.bd-error {
  padding:8px 12px;
  border-radius:6px;
  font-size:12px;
  color:var(--danger);
  background:#ff4d4f14;
  border:1px solid rgba(255,77,79,.2)
}
.bd-info {
  margin-top:4px
}
.bd-qr-section {
  margin-top:8px
}
.bd-qr-title {
  font-size:14px;
  font-weight:600;
  color:var(--text);
  margin-bottom:8px
}
.bd-qr-row {
  display:flex;
  gap:24px;
  justify-content:center
}
.bd-qr-item {
  text-align:center
}
.bd-qr-label {
  font-size:12px;
  color:var(--text2);
  margin-bottom:6px
}
.bd-qr-img {
  width:160px;
  height:160px;
  border-radius:8px;
  border:1px solid var(--border);
  background:#fff;
  padding:4px
}
.bd-qr-link {
  display:block;
  margin-top:6px;
  font-size:11px;
  color:var(--accent);
  text-decoration:none
}
.bd-qr-link:hover {
  text-decoration:underline
}
@media(max-width:767px) {
  .sidebar {
  position:fixed;
  left:0;
  top:0;
  bottom:0;
  width:260px;
  transform:translate(-100%)
}
.sidebar.open {
  transform:translate(0)
}
.content {
  padding:12px
}
.topbar {
  padding:0 10px
}
.topbar-left {
  flex:1;
  min-width:0;
  overflow:hidden
}
.bot-selector {
  flex:1;
  min-width:0;
  overflow:hidden
}
.bot-selector .bot-name {
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  max-width:100px
}
.topbar-right {
  flex-shrink:0
}
.bd-header {
  flex-direction:column;
  text-align:center
}
.bd-qr-row {
  flex-direction:column;
  align-items:center
}
}
</style>
