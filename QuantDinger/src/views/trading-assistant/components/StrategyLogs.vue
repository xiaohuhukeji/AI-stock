<template>
  <div class="strategy-logs strategy-tab-pane-inner" :class="{ 'theme-dark': isDark }">
    <div class="logs-toolbar">
      <div class="toolbar-left">
        <div class="log-filter-tabs">
          <div
            v-for="item in filterOptions"
            :key="item.value"
            class="log-filter-tab"
            :class="[
              'tab-' + item.value,
              { active: filterLevel === item.value }
            ]"
            @click="filterLevel = item.value"
          >
            <a-icon :type="item.icon" class="tab-icon" />
            <span class="tab-label">{{ item.label }}</span>
            <span v-if="item.value !== 'all' && countByLevel(item.value) > 0" class="tab-count">
              {{ countByLevel(item.value) > 99 ? '99+' : countByLevel(item.value) }}
            </span>
            <span v-if="item.value === 'all' && logs.length > 0" class="tab-count">
              {{ logs.length > 99 ? '99+' : logs.length }}
            </span>
          </div>
        </div>
      </div>
      <div class="toolbar-right">
        <a-button
          type="link"
          size="small"
          :loading="clearing"
          @click="handleClearLogs"
          class="clear-btn"
        >
          <a-icon type="delete" />
          {{ $t('trading-assistant.logs.clearLogs') || '清除日志' }}
        </a-button>
        <a-switch
          :checked="autoRefresh"
          @change="toggleAutoRefresh"
          size="small"
        />
        <span class="auto-refresh-label">{{ $t('trading-assistant.logs.autoRefresh') }}</span>
      </div>
    </div>

    <div class="logs-container custom-scrollbar" ref="logsContainer">
      <div v-if="displayLogs.length === 0" class="logs-empty">
        <a-icon type="file-text" style="font-size: 32px; color: #ccc;" />
        <p>{{ $t('trading-assistant.logs.noLogs') }}</p>
      </div>
      <div
        v-for="(log, idx) in displayLogs"
        :key="idx"
        class="log-entry"
        :class="'level-' + log.level"
      >
        <span class="log-time">{{ formatTime(log.timestamp) }}</span>
        <a-tag :color="getLevelColor(log.level)" size="small" class="log-level">
          {{ getLevelText(log.level) }}
        </a-tag>
        <span class="log-message">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import request from '@/utils/request'
import { formatStrategyLogTime } from '@/utils/userTime'

export default {
  name: 'StrategyLogs',
  props: {
    strategyId: { type: [Number, String], default: null },
    isDark: { type: Boolean, default: false }
  },
  data () {
    return {
      logs: [],
      filterLevel: 'all',
      autoRefresh: false,
      refreshTimer: null,
      loading: false,
      clearing: false
    }
  },
  computed: {
    filterOptions () {
      return [
        { value: 'all', label: this.$t('trading-assistant.logs.level.all') || '全部', icon: 'bars' },
        { value: 'trade', label: this.$t('trading-assistant.logs.level.trade') || '交易', icon: 'transaction' },
        { value: 'signal', label: this.$t('trading-assistant.logs.level.signal') || '信号', icon: 'notification' },
        { value: 'error', label: this.$t('trading-assistant.logs.level.error') || '错误', icon: 'warning' }
      ]
    },
    filteredLogs () {
      if (this.filterLevel === 'all') return this.logs
      return this.logs.filter(l => l.level === this.filterLevel)
    },
    /** Newest entries first (API returns id DESC). */
    displayLogs () {
      return this.filteredLogs.slice()
    }
  },
  watch: {
    strategyId: {
      handler (val) {
        if (val) this.loadLogs()
      },
      immediate: true
    }
  },
  beforeDestroy () {
    this.stopAutoRefresh()
  },
  methods: {
    async loadLogs () {
      if (!this.strategyId) return
      this.loading = true
      try {
        const res = await request({
          url: '/api/strategies/logs',
          method: 'get',
          params: { id: this.strategyId, limit: 200 }
        })
        if (res && res.data) {
          this.logs = res.data
          this.$nextTick(() => this.scrollToTop())
        }
      } catch (e) {
        console.warn('Load logs failed:', e)
      } finally {
        this.loading = false
      }
    },

    toggleAutoRefresh (checked) {
      this.autoRefresh = checked
      if (checked) {
        this.refreshTimer = setInterval(() => this.loadLogs(), 5000)
      } else {
        this.stopAutoRefresh()
      }
    },

    stopAutoRefresh () {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer)
        this.refreshTimer = null
      }
    },

    scrollToTop () {
      const el = this.$refs.logsContainer
      if (el) el.scrollTop = 0
    },

    countByLevel (level) {
      return this.logs.filter(l => l.level === level).length
    },

    formatTime (ts) {
      if (!ts) return ''
      const loc = this.$i18n.locale || 'zh-CN'
      const profileTz = (this.$store.getters.userInfo || {}).timezone
      return formatStrategyLogTime(ts, {
        locale: loc,
        timeZone: profileTz,
        fallback: String(ts)
      })
    },

    getLevelColor (level) {
      const map = { info: 'blue', warn: 'orange', error: 'red', trade: 'green', signal: 'purple' }
      return map[level] || 'default'
    },

    getLevelText (level) {
      const key = `trading-assistant.logs.level.${level}`
      const translated = this.$t(key)
      return translated !== key ? translated : level
    },

    async handleClearLogs () {
      if (!this.strategyId) return
      this.$confirm({
        title: this.$t('trading-assistant.logs.clearConfirmTitle') || '确认清除',
        content: this.$t('trading-assistant.logs.clearConfirmContent') || '确定要清除所有日志吗？此操作不可恢复。',
        okText: this.$t('common.confirm') || '确定',
        okType: 'danger',
        cancelText: this.$t('common.cancel') || '取消',
        onOk: async () => {
          this.clearing = true
          try {
            const res = await request({
              url: '/api/strategies/logs',
              method: 'delete',
              params: { id: this.strategyId }
            })
            if (res && res.code === 1) {
              this.$message.success(res.msg || '日志已清除')
              this.logs = []
            } else {
              this.$message.error(res.msg || '清除失败')
            }
          } catch (e) {
            console.warn('Clear logs failed:', e)
            this.$message.error('清除日志失败')
          } finally {
            this.clearing = false
          }
      }
    })
  }
}
}
</script>

<style lang="less" scoped>
.strategy-logs {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.logs-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  margin-bottom: 8px;

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 6px;

    .clear-btn {
      padding: 0 8px;
      font-size: 12px;
      color: #999;
      &:hover {
        color: #ff4d4f;
      }
    }

    .auto-refresh-label {
      font-size: 12px;
      color: #999;
    }
  }
}

.log-filter-tabs {
  display: flex;
  gap: 6px;
}

.log-filter-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  border: 1px solid transparent;
  line-height: 1.5;

  .tab-icon {
    font-size: 13px;
    transition: transform 0.2s;
  }

  .tab-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    border-radius: 9px;
    font-size: 10px;
    font-weight: 600;
    line-height: 1;
  }

  &:hover .tab-icon {
    transform: scale(1.15);
  }

  // All
  &.tab-all {
    color: #595959;
    background: #f5f5f5;
    border-color: #e8e8e8;
    .tab-count { background: #e0e0e0; color: #595959; }
    &:hover { background: #ebebeb; }
    &.active {
      color: #1890ff;
      background: #e6f7ff;
      border-color: #91d5ff;
      .tab-count { background: #1890ff; color: #fff; }
    }
  }

  // Trade
  &.tab-trade {
    color: #389e0d;
    background: #f6ffed;
    border-color: #d9f7be;
    .tab-count { background: #d9f7be; color: #389e0d; }
    &:hover { background: #eaffdb; }
    &.active {
      color: #fff;
      background: linear-gradient(135deg, #52c41a, #389e0d);
      border-color: transparent;
      box-shadow: 0 2px 8px rgba(82, 196, 26, 0.35);
      .tab-count { background: rgba(255, 255, 255, 0.3); color: #fff; }
    }
  }

  // Signal
  &.tab-signal {
    color: #531dab;
    background: #f9f0ff;
    border-color: #d3adf7;
    .tab-count { background: #d3adf7; color: #531dab; }
    &:hover { background: #f0e0ff; }
    &.active {
      color: #fff;
      background: linear-gradient(135deg, #9254de, #722ed1);
      border-color: transparent;
      box-shadow: 0 2px 8px rgba(114, 46, 209, 0.35);
      .tab-count { background: rgba(255, 255, 255, 0.3); color: #fff; }
    }
  }

  // Error
  &.tab-error {
    color: #d93026;
    background: #fff2f0;
    border-color: #ffccc7;
    .tab-count { background: #ffccc7; color: #d93026; }
    &:hover { background: #ffece8; }
    &.active {
      color: #fff;
      background: linear-gradient(135deg, #ff4d4f, #d93026);
      border-color: transparent;
      box-shadow: 0 2px 8px rgba(217, 48, 38, 0.35);
      .tab-count { background: rgba(255, 255, 255, 0.3); color: #fff; }
    }
  }
}

.logs-container {
  flex: 1;
  min-height: 300px;
  max-height: 500px;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.7;
  background: #fafafa;
}

.logs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #ccc;

  p {
    margin-top: 8px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 2px 4px;
  border-radius: 3px;

  &:hover {
    background: rgba(0, 0, 0, 0.02);
  }

  &.level-error {
    background: rgba(255, 77, 79, 0.04);
  }

  &.level-trade {
    background: rgba(82, 196, 26, 0.04);
  }
}

.log-time {
  color: #999;
  white-space: nowrap;
  font-size: 11px;
  min-width: 65px;
}

.log-level {
  flex-shrink: 0;
  font-size: 10px;
}

.log-message {
  flex: 1;
  word-break: break-all;
}

.theme-dark {
  .logs-toolbar {
    .toolbar-right .auto-refresh-label {
      color: rgba(255, 255, 255, 0.4);
    }
  }

  .log-filter-tab {
    &.tab-all {
      color: rgba(255, 255, 255, 0.6);
      background: rgba(255, 255, 255, 0.06);
      border-color: rgba(255, 255, 255, 0.1);
      .tab-count { background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.5); }
      &:hover { background: rgba(255, 255, 255, 0.1); }
      &.active {
        color: #40a9ff;
        background: rgba(24, 144, 255, 0.15);
        border-color: rgba(24, 144, 255, 0.4);
        .tab-count { background: #1890ff; color: #fff; }
      }
    }
    &.tab-trade {
      color: #73d13d;
      background: rgba(82, 196, 26, 0.08);
      border-color: rgba(82, 196, 26, 0.2);
      .tab-count { background: rgba(82, 196, 26, 0.15); color: #73d13d; }
      &:hover { background: rgba(82, 196, 26, 0.14); }
      &.active {
        color: #fff;
        background: linear-gradient(135deg, #52c41a, #389e0d);
        border-color: transparent;
        box-shadow: 0 2px 10px rgba(82, 196, 26, 0.4);
        .tab-count { background: rgba(255, 255, 255, 0.25); color: #fff; }
      }
    }
    &.tab-signal {
      color: #b37feb;
      background: rgba(114, 46, 209, 0.08);
      border-color: rgba(114, 46, 209, 0.2);
      .tab-count { background: rgba(114, 46, 209, 0.15); color: #b37feb; }
      &:hover { background: rgba(114, 46, 209, 0.14); }
      &.active {
        color: #fff;
        background: linear-gradient(135deg, #9254de, #722ed1);
        border-color: transparent;
        box-shadow: 0 2px 10px rgba(114, 46, 209, 0.4);
        .tab-count { background: rgba(255, 255, 255, 0.25); color: #fff; }
      }
    }
    &.tab-error {
      color: #ff7875;
      background: rgba(255, 77, 79, 0.08);
      border-color: rgba(255, 77, 79, 0.2);
      .tab-count { background: rgba(255, 77, 79, 0.15); color: #ff7875; }
      &:hover { background: rgba(255, 77, 79, 0.14); }
      &.active {
        color: #fff;
        background: linear-gradient(135deg, #ff4d4f, #cf1322);
        border-color: transparent;
        box-shadow: 0 2px 10px rgba(255, 77, 79, 0.4);
        .tab-count { background: rgba(255, 255, 255, 0.25); color: #fff; }
      }
    }
  }

  .logs-container {
    background: #141414;
    border-color: rgba(255, 255, 255, 0.08);
  }

  .logs-empty {
    color: rgba(255, 255, 255, 0.25);

    .anticon {
      color: rgba(255, 255, 255, 0.15) !important;
    }

    p {
      color: rgba(255, 255, 255, 0.3);
    }
  }

  .log-entry {
    &:hover {
      background: rgba(255, 255, 255, 0.03);
    }

    &.level-error {
      background: rgba(255, 77, 79, 0.06);
    }

    &.level-trade {
      background: rgba(82, 196, 26, 0.06);
    }
  }

  .log-time {
    color: rgba(255, 255, 255, 0.3);
  }

  .log-message {
    color: rgba(255, 255, 255, 0.75);
  }
}
</style>
