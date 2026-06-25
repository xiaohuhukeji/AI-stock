<template>
  <div class="strategy-reference strategy-tab-pane-inner" :class="{ 'theme-dark': isDark }">
    <div v-if="loading" class="reference-loading">
      <a-spin :size="'large'" />
    </div>
    <div v-else-if="!referenceData" class="reference-empty">
      <a-icon type="file-search" style="font-size: 32px; color: #ccc;" />
      <p>暂无参考数据</p>
    </div>
    <div v-else class="reference-content">
      <div class="reference-header">
        <div class="header-title">
          <a-icon type="line-chart" class="title-icon" />
          <span>参考价格</span>
        </div>
        <div class="header-info">
          <span class="info-item">
            <span class="info-label">策略:</span>
            <span class="info-value">{{ strategyInfo ? strategyInfo.strategy_name : '-' }}</span>
          </span>
          <span class="info-item">
            <span class="info-label">标的:</span>
            <span class="info-value">{{ currentSymbol }}</span>
          </span>
          <span class="info-item">
            <span class="info-label">当前价格:</span>
            <span class="info-value current-price">{{ referenceData.current_price.toFixed(2) }}</span>
          </span>
        </div>
      </div>

      <div class="reference-stats">
        <div class="stat-card">
          <div class="stat-icon buy-icon">
            <a-icon type="arrow-down" />
          </div>
          <div class="stat-info">
            <div class="stat-label">买入参考价</div>
            <div class="stat-value buy-value">{{ referenceData.buy_price.toFixed(2) }}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon sell-icon">
            <a-icon type="arrow-up" />
          </div>
          <div class="stat-info">
            <div class="stat-label">卖出参考价</div>
            <div class="stat-value sell-value">{{ referenceData.sell_price.toFixed(2) }}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stop-icon">
            <a-icon type="warning" />
          </div>
          <div class="stat-info">
            <div class="stat-label">止损参考价</div>
            <div class="stat-value stop-value">{{ referenceData.stop_loss ? referenceData.stop_loss.toFixed(2) : '-' }}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon profit-icon">
            <a-icon type="rise" />
          </div>
          <div class="stat-info">
            <div class="stat-label">止盈参考价</div>
            <div class="stat-value profit-value">{{ referenceData.take_profit ? referenceData.take_profit.toFixed(2) : '-' }}</div>
          </div>
        </div>
      </div>

      <div v-if="referenceData.signals && referenceData.signals.length > 0" class="reference-signals">
        <div class="signals-header">
          <span class="signals-title">当前信号</span>
        </div>
        <div class="signals-list">
          <div v-for="(signal, idx) in referenceData.signals" :key="idx" class="signal-item">
            <a-tag :color="getSignalColor(signal.type)" size="small">{{ getTradeText(signal.type) }}</a-tag>
            <span v-if="signal.price" class="signal-price">{{ signal.price.toFixed(2) }}</span>
            <span v-if="signal.reason" class="signal-reason">{{ signal.reason }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import request from '@/utils/request'

export default {
  name: 'StrategyReference',
  props: {
    strategyId: { type: [Number, String], default: null },
    isDark: { type: Boolean, default: false },
    strategyInfo: { type: Object, default: null }
  },
  data () {
    return {
      loading: false,
      referenceData: null
    }
  },
  computed: {
    currentSymbol () {
      return (this.strategyInfo && this.strategyInfo.trading_config && this.strategyInfo.trading_config.symbol) || ''
    }
  },
  watch: {
    strategyId: {
      handler (val) {
        if (val) this.loadReferenceData()
      },
      immediate: true
    }
  },
  methods: {
    async loadReferenceData () {
      if (!this.strategyId) return
      this.loading = true
      this.referenceData = null
      try {
        const res = await request({
          url: '/api/strategies/reference-price',
          method: 'get',
          params: { strategyId: this.strategyId }
        })
        if (res && res.code === 1 && res.data) {
          this.referenceData = res.data
        }
      } finally {
        this.loading = false
      }
    },
    getSignalColor (type) {
      if (!type) return 'default'
      if (type.startsWith('open') || type === 'buy') return 'green'
      if (type.startsWith('close_long_stop') || type.startsWith('close_short_stop')) return 'orange'
      if (type.startsWith('close_long_tp') || type.startsWith('close_short_tp')) return 'blue'
      if (type.startsWith('close') || type === 'sell') return 'red'
      return 'default'
    },
    getTradeText (type) {
      const map = {
        'open_long': '开多',
        'close_long': '平多',
        'close_long_stop': '止损平多',
        'close_long_tp': '止盈平多',
        'close_long_trailing': '移动止盈平多',
        'close_long_tr': '移动止盈平多',
        'open_short': '开空',
        'close_short': '平空',
        'close_short_stop': '止损平空',
        'close_short_tp': '止盈平空',
        'close_short_trailing': '移动止盈平空',
        'close_short_tr': '移动止盈平空',
        'reduce_long': '减多',
        'reduce_short': '减空',
        'add_long': '加多',
        'add_short': '加空'
      }
      return map[type] || type
    },
    formatDate (date) {
      if (!date) return '-'
      let d
      if (typeof date === 'string') {
        const parts = date.split(/[\s-:]/)
        if (parts.length >= 5) {
          d = new Date(
            parseInt(parts[0]),
            parseInt(parts[1]) - 1,
            parseInt(parts[2]),
            parseInt(parts[3]),
            parseInt(parts[4])
          )
        } else {
          d = new Date(date)
        }
      } else {
        d = new Date(date)
      }
      if (isNaN(d.getTime())) return date
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      const h = String(d.getHours()).padStart(2, '0')
      const min = String(d.getMinutes()).padStart(2, '0')
      return `${y}-${m}-${day} ${h}:${min}`
    }
  }
}
</script>

<style lang="less" scoped>
.strategy-reference {
  padding: 12px 0;

  .reference-loading {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 40px 0;
  }

  .reference-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    color: #999;

    p {
      margin-top: 8px;
    }

    .empty-tip {
      font-size: 12px;
      color: #bbb;
    }
  }

  .reference-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .reference-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: linear-gradient(135deg, #f0f5ff, #e6f7ff);
    border-radius: 8px;
    border: 1px solid #91d5ff;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
      color: #1890ff;

      .title-icon {
        font-size: 20px;
      }
    }

    .header-info {
      display: flex;
      gap: 20px;
      font-size: 13px;

      .info-item {
        display: flex;
        gap: 4px;

        .info-label {
          color: #666;
        }

        .info-value {
          color: #333;
          font-weight: 500;

          &.mismatch {
            color: #faad14;
          }

          &.current-price {
            color: #1890ff;
            font-size: 14px;
          }
        }
      }
    }
  }

  .reference-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;

    .stat-card {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      background: #fff;
      border: 1px solid #e8e8e8;
      border-radius: 8px;
      transition: all 0.2s;

      &:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      }

      .stat-icon {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        color: #fff;

        &.buy-icon {
          background: linear-gradient(135deg, #52c41a, #73d13d);
        }

        &.sell-icon {
          background: linear-gradient(135deg, #ff4d4f, #ff7875);
        }

        &.profit-icon {
          background: linear-gradient(135deg, #1890ff, #40a9ff);
        }

        &.stop-icon {
          background: linear-gradient(135deg, #fa8c16, #ffa940);
        }

        &.count-icon {
          background: linear-gradient(135deg, #fa8c16, #ffa940);
        }
      }

      .stat-info {
        flex: 1;

        .stat-label {
          font-size: 12px;
          color: #999;
          margin-bottom: 4px;
        }

        .stat-value {
          font-size: 20px;
          font-weight: 600;
          font-family: 'Fira Code', 'Consolas', monospace;

          &.buy-value {
            color: #52c41a;
          }

          &.sell-value {
            color: #ff4d4f;
          }

          &.profit-value {
            color: #1890ff;
          }

          &.stop-value {
            color: #fa8c16;
          }

          &.count-value {
            color: #fa8c16;
          }
        }
      }
    }
  }

  .reference-signals {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    padding: 12px 16px;

    .signals-header {
      margin-bottom: 8px;

      .signals-title {
        font-size: 14px;
        font-weight: 600;
        color: #333;
      }
    }

    .signals-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .signal-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: #f5f5f5;
        border-radius: 4px;

        .signal-price {
          font-family: 'Fira Code', 'Consolas', monospace;
          font-weight: 600;
          color: #333;
        }

        .signal-reason {
          font-size: 12px;
          color: #999;
        }
      }
    }
  }

  .reference-trades {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    overflow: hidden;

    .trades-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #f0f0f0;
      background: #fafafa;

      .trades-title {
        font-size: 14px;
        font-weight: 600;
        color: #333;
      }

      .trades-count {
        font-size: 12px;
        color: #999;
      }
    }

    .trades-table {
      max-height: 400px;
      overflow-y: auto;

      .trades-row {
        display: grid;
        grid-template-columns: 50px 80px 1fr 1fr 1.5fr;
        gap: 0;
        padding: 10px 16px;
        border-bottom: 1px solid #f5f5f5;
        font-size: 13px;
        transition: background 0.2s;

        &:hover {
          background: #fafafa;
        }

        &:last-child {
          border-bottom: none;
        }

        &.trades-header-row {
          background: #fafafa;
          font-weight: 600;
          color: #666;
          font-size: 12px;
          position: sticky;
          top: 0;
          z-index: 1;
        }

        .trades-col {
          display: flex;
          align-items: center;

          &.col-index {
            color: #999;
          }

          &.price-value {
            font-family: 'Fira Code', 'Consolas', monospace;
            font-weight: 500;
          }
        }

        &.trade-open_long,
        &.trade-open_short {
          .price-value {
            color: #52c41a;
          }
        }

        &.trade-close_long,
        &.trade-close_short {
          .price-value {
            color: #ff4d4f;
          }
        }
      }
    }

    .trades-more {
      text-align: center;
      padding: 8px;
      border-top: 1px solid #f0f0f0;
    }
  }
}

.theme-dark.strategy-reference {
  .reference-header {
    background: linear-gradient(135deg, rgba(24, 144, 255, 0.1), rgba(24, 144, 255, 0.05));
    border-color: rgba(24, 144, 255, 0.3);

    .header-title {
      color: #40a9ff;
    }

    .header-info .info-label {
      color: rgba(255, 255, 255, 0.5);
    }

    .header-info .info-value {
      color: rgba(255, 255, 255, 0.85);

      &.mismatch {
        color: #faad14;
      }
    }
  }

  .reference-stats .stat-card {
    background: #141414;
    border-color: rgba(255, 255, 255, 0.08);

    .stat-info .stat-label {
      color: rgba(255, 255, 255, 0.45);
    }
  }

  .reference-trades {
    background: #141414;
    border-color: rgba(255, 255, 255, 0.08);

    .trades-header {
      background: rgba(255, 255, 255, 0.02);
      border-color: rgba(255, 255, 255, 0.08);

      .trades-title {
        color: rgba(255, 255, 255, 0.85);
      }

      .trades-count {
        color: rgba(255, 255, 255, 0.45);
      }
    }

    .trades-table .trades-row {
      border-color: rgba(255, 255, 255, 0.06);
      color: rgba(255, 255, 255, 0.75);

      &:hover {
        background: rgba(255, 255, 255, 0.02);
      }

      &.trades-header-row {
        background: rgba(255, 255, 255, 0.04);
        color: rgba(255, 255, 255, 0.65);
      }

      .col-index {
        color: rgba(255, 255, 255, 0.45);
      }
    }

    .trades-more {
      border-color: rgba(255, 255, 255, 0.08);
    }
  }

  .reference-empty {
    color: rgba(255, 255, 255, 0.45);

    .empty-tip {
      color: rgba(255, 255, 255, 0.3);
    }
  }
}
</style>
