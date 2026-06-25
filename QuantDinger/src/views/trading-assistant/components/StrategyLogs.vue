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

    <div v-if="manualAlertVisible && manualAlertData" class="manual-alert-panel">
      <div class="alert-header">
        <a-icon type="bell" class="alert-icon" />
        <span class="alert-title">手动操作提示</span>
        <a-button type="link" size="small" @click="manualAlertVisible = false">
          <a-icon type="close" />
        </a-button>
      </div>
      <div class="alert-content">
        <div class="alert-row">
          <span class="alert-label">标的</span>
          <span class="alert-value">{{ manualAlertData.symbol }} {{ manualAlertData.name }}</span>
        </div>
        <div class="alert-row">
          <span class="alert-label">当前价格</span>
          <span class="alert-value price-value">{{ manualAlertData.price }}</span>
        </div>
        <div class="alert-row">
          <span class="alert-label">提醒时间</span>
          <span class="alert-value">{{ manualAlertData.alertTime }}</span>
        </div>
        <div class="alert-row">
          <span class="alert-label">交易时段</span>
          <span class="alert-value">{{ manualAlertData.session }}</span>
        </div>
        <div class="alert-tip">
          <a-icon type="info-circle" />
          <span>建议提前下单，避免开盘价波动影响成交</span>
        </div>
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
        <span v-if="log.reference_price && log.reference_price > 0" class="log-reference-price">
          <span class="ref-price-label">参考价:</span>
          <span class="ref-price-value">{{ log.reference_price.toFixed(2) }}</span>
        </span>
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
    isDark: { type: Boolean, default: false },
    strategyInfo: { type: Object, default: null }
  },
  data () {
    return {
      logs: [],
      filterLevel: 'all',
      autoRefresh: false,
      refreshTimer: null,
      loading: false,
      clearing: false,
      manualAlertVisible: false,
      manualAlertData: null,
      manualAlertTimer: null,
      lastAlertTime: null,
      priceCache: {}
    }
  },
  computed: {
    filterOptions () {
      return [
        { value: 'all', label: this.$t('trading-assistant.logs.level.all') || '全部', icon: 'bars' },
        { value: 'trade', label: this.$t('trading-assistant.logs.level.trade') || '交易', icon: 'transaction' },
        { value: 'signal', label: this.$t('trading-assistant.logs.level.signal') || '信号', icon: 'notification' },
        { value: 'manual', label: this.$t('trading-assistant.logs.level.manual') || '手动操作提示', icon: 'bell' },
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
    },
    /** Strategy execution mode: 'live' = auto trade, 'signal' = manual only. */
    executionMode () {
      return (this.strategyInfo && this.strategyInfo.execution_mode) || 'signal'
    },
    /** K线周期 (e.g., "15m", "1H"). Default to "15m" if missing. */
    timeframe () {
      return (this.strategyInfo && this.strategyInfo.trading_config && this.strategyInfo.trading_config.timeframe) || '15m'
    },
    /** Convert timeframe string to seconds. */
    timeframeSeconds () {
      const tf = String(this.timeframe || '15m').trim().toLowerCase()
      const m = /^(\d+)\s*(s|m|h|d)$/.exec(tf)
      if (!m) return 900
      const n = parseInt(m[1], 10)
      const unit = m[2]
      if (unit === 's') return n
      if (unit === 'm') return n * 60
      if (unit === 'h') return n * 3600
      if (unit === 'd') return n * 86400
      return 900
    },
    /** Whether this strategy is in "signal-only" mode (manual trading). */
    isSignalMode () {
      return String(this.executionMode || '').toLowerCase() !== 'live'
    },
    isCNStockStrategy () {
      if (!this.strategyInfo) return false
      const cat = (this.strategyInfo.trading_config && this.strategyInfo.trading_config.market_type) || ''
      return String(cat).toLowerCase() === 'cnstock' || /^\d{6}\.SH$|^\d{6}\.SZ$|^\d{6}$/.test(this.currentSymbol)
    },
    currentSymbol () {
      return (this.strategyInfo && this.strategyInfo.trading_config && this.strategyInfo.trading_config.symbol) || ''
    }
  },
  watch: {
    strategyId: {
      handler (val) {
        if (val) this.loadLogs()
      },
      immediate: true
    },
    strategyInfo: {
      handler () {
        this.startManualAlertCheck()
      },
      immediate: true
    }
  },
  mounted () {
    this.startManualAlertCheck()
  },
  beforeDestroy () {
    this.stopAutoRefresh()
    this.stopManualAlertCheck()
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
      const map = { info: 'blue', warn: 'orange', error: 'red', trade: 'green', signal: 'purple', manual: 'gold' }
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
    },

    startManualAlertCheck () {
      this.stopManualAlertCheck()
      // 只支持 A股 手动信号模式.
      if (!this.isCNStockStrategy) return
      if (!this.isSignalMode) return
      if (!this.currentSymbol) return
      // 30s 轮询; K线开始的60s窗口内触发一次.
      this.checkKlineBoundaryAlert()
      this.manualAlertTimer = setInterval(() => {
        this.checkKlineBoundaryAlert()
      }, 30000)
    },

    stopManualAlertCheck () {
      if (this.manualAlertTimer) {
        clearInterval(this.manualAlertTimer)
        this.manualAlertTimer = null
      }
    },

    /**
     * A股 K线开始时提醒（给用户 timeframe 分钟的时间在K线收盘前手动下单）.
     * 仅工作日 & A股交易时段内触发.
     *
     *   - 15m K线: 9:30 开始 → 9:45 结束 → 在 9:30 提醒.
     *   - 15m K线: 13:00 开始 → 13:15 结束 → 在 13:00 提醒.
     */
    checkKlineBoundaryAlert () {
      const now = new Date()
      const day = now.getDay()
      // 周末不提醒.
      if (day === 0 || day === 6) return

      const hours = now.getHours()
      const minutes = now.getMinutes()
      const totalMinutes = hours * 60 + minutes
      // A股交易时段: 上午 9:30-11:30, 下午 13:00-15:00.
      const morningStart = 9 * 60 + 30
      const morningEnd = 11 * 60 + 30
      const afternoonStart = 13 * 60 + 0
      const afternoonEnd = 15 * 60 + 0
      const inTradingHours =
        (totalMinutes >= morningStart && totalMinutes < morningEnd) ||
        (totalMinutes >= afternoonStart && totalMinutes < afternoonEnd)
      if (!inTradingHours) return

      const nowTs = now.getTime()
      const tfSec = this.timeframeSeconds
      if (!tfSec || tfSec < 60) return

      const nowSec = Math.floor(nowTs / 1000)
      // K线边界按 Unix epoch 对齐.
      const currentBarEnd = Math.floor(nowSec / tfSec) * tfSec
      const currentBarStart = currentBarEnd - tfSec
      const secSinceOpen = nowSec - currentBarStart
      const secToClose = currentBarEnd - nowSec

      // 提醒窗口 = K线开始后 60 秒内（刚开盘时）.
      const windowSec = 60
      const inAlertWindow = secSinceOpen >= 0 && secSinceOpen <= windowSec
      if (!inAlertWindow) return

      // 每个 (K线, 策略) 每个 bar 最多提醒一次.
      const alertKey = `${this.currentSymbol}_${currentBarEnd}`
      if (this.lastAlertTime === alertKey) return
      this.lastAlertTime = alertKey

      const minToClose = Math.floor(secToClose / 60)
      this.showKlineAlert({
        symbol: this.currentSymbol,
        name: (this.strategyInfo && this.strategyInfo.strategy_name) || '',
        timeframe: this.timeframe,
        currentBarStart: this._formatTime(currentBarStart),
        currentBarEnd: this._formatTime(currentBarEnd),
        minToClose: minToClose,
        nowDate: now
      })
    },

    _formatTime (epochSec) {
      const d = new Date(epochSec * 1000)
      const hh = String(d.getHours()).padStart(2, '0')
      const mm = String(d.getMinutes()).padStart(2, '0')
      return `${hh}:${mm}`
    },

    async showKlineAlert (info) {
      try {
        const res = await request({
          url: '/api/market/price',
          method: 'get',
          params: {
            market: (this.strategyInfo.trading_config && this.strategyInfo.trading_config.market_type) || 'CNStock',
            symbol: info.symbol
          }
        })
        if (res && res.code === 1 && res.data) {
          const price = parseFloat(res.data.price || 0)
          if (price > 0) {
            this.priceCache[info.symbol] = price
            const alertTime = `${String(info.nowDate.getHours()).padStart(2, '0')}:${String(info.nowDate.getMinutes()).padStart(2, '0')}`
            this.manualAlertData = {
              symbol: info.symbol,
              name: info.name,
              price: price.toFixed(2),
              alertTime: alertTime,
              timeframe: info.timeframe,
              barStart: info.currentBarStart,
              barEnd: info.currentBarEnd,
              minToClose: info.minToClose,
              session: `${info.currentBarStart} - ${info.currentBarEnd}`
            }
            this.manualAlertVisible = true
            this.$notification.warning({
              message: '手动操作提示',
              description: `${info.symbol} ${info.timeframe}K线将在 ${info.minToClose} 分钟后于 ${info.currentBarEnd} 收盘，当前价格：${price.toFixed(2)}，请提前手动下单`,
              duration: 15
            })
            try {
              await request({
                url: '/api/strategies/notifications/manual-alert',
                method: 'post',
                data: {
                  strategy_id: this.strategyId,
                  symbol: info.symbol,
                  price: price,
                  session: `${info.timeframe} K线 (${info.currentBarStart}-${info.currentBarEnd})`,
                  alert_time: alertTime
                }
              })
            } catch (notifyErr) {
              console.warn('Send manual alert notification failed:', notifyErr)
            }
          }
        }
      } catch (e) {
        console.warn('Get price failed:', e)
      }
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

  // Manual
  &.tab-manual {
    color: #fa8c16;
    background: #fffbe6;
    border-color: #ffe58f;
    .tab-count { background: #ffe58f; color: #fa8c16; }
    &:hover { background: #fff7d6; }
    &.active {
      color: #fff;
      background: linear-gradient(135deg, #faad14, #fa8c16);
      border-color: transparent;
      box-shadow: 0 2px 8px rgba(250, 140, 22, 0.35);
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

.log-reference-price {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  padding: 2px 6px;
  background: linear-gradient(135deg, #e6f7ff, #f0f5ff);
  border: 1px solid #91d5ff;
  border-radius: 4px;
  font-size: 11px;

  .ref-price-label {
    color: #1890ff;
    font-weight: 500;
  }

  .ref-price-value {
    color: #1890ff;
    font-weight: 600;
    font-family: 'Fira Code', 'Consolas', monospace;
  }
}

.manual-alert-panel {
  background: linear-gradient(135deg, #fffbe6, #fff7e6);
  border: 1px solid #ffe58f;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;

  .alert-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px dashed #ffe58f;

    .alert-icon {
      font-size: 18px;
      color: #fa8c16;
      margin-right: 8px;
    }

    .alert-title {
      font-size: 14px;
      font-weight: 600;
      color: #fa8c16;
    }
  }

  .alert-content {
    .alert-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 6px 0;

      .alert-label {
        font-size: 12px;
        color: #8c8c8c;
        min-width: 60px;
      }

      .alert-value {
        font-size: 12px;
        color: #333;
        font-weight: 500;

        &.price-value {
          font-size: 16px;
          color: #fa8c16;
          font-weight: 600;
        }
      }
    }

    .alert-tip {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 12px;
      padding-top: 8px;
      border-top: 1px dashed #ffe58f;
      font-size: 11px;
      color: #fa8c16;

      .anticon {
        font-size: 12px;
      }
    }
  }
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
    &.tab-manual {
      color: #ffa940;
      background: rgba(250, 140, 22, 0.08);
      border-color: rgba(250, 140, 22, 0.2);
      .tab-count { background: rgba(250, 140, 22, 0.15); color: #ffa940; }
      &:hover { background: rgba(250, 140, 22, 0.14); }
      &.active {
        color: #fff;
        background: linear-gradient(135deg, #faad14, #fa8c16);
        border-color: transparent;
        box-shadow: 0 2px 10px rgba(250, 140, 22, 0.4);
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

  .log-reference-price {
    background: rgba(24, 144, 255, 0.1);
    border-color: rgba(24, 144, 255, 0.3);

    .ref-price-label {
      color: #40a9ff;
    }

    .ref-price-value {
      color: #40a9ff;
    }
  }

  .manual-alert-panel {
    background: rgba(250, 140, 22, 0.08);
    border-color: rgba(250, 140, 22, 0.2);

    .alert-header {
      border-bottom-color: rgba(250, 140, 22, 0.2);

      .alert-icon {
        color: #ffa940;
      }

      .alert-title {
        color: #ffa940;
      }
    }

    .alert-content {
      .alert-row {
        .alert-label {
          color: rgba(255, 255, 255, 0.4);
        }

        .alert-value {
          color: rgba(255, 255, 255, 0.75);

          &.price-value {
            color: #ffa940;
          }
        }
      }

      .alert-tip {
        border-top-color: rgba(250, 140, 22, 0.2);
        color: #ffa940;
      }
    }
  }
}
</style>
