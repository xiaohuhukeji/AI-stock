<template>
  <div class="ai-stock-screener" :class="{ 'theme-dark': isDarkTheme }">
    <div class="screener-header">
      <div class="header-left">
        <div class="header-icon">
          <a-icon type="stock" />
        </div>
        <div class="header-text">
          <h1 class="page-title">{{ $t('aiStockScreener.pageTitle') }}</h1>
          <p class="page-subtitle">{{ $t('aiStockScreener.pageSubtitle') }}</p>
        </div>
      </div>
      <div class="header-actions">
        <a-button-group>
          <a-button :type="activeTab === 'filters' ? 'primary' : 'default'" @click="activeTab = 'filters'">
            <a-icon type="filter" /> {{ $t('aiStockScreener.filterMode') }}
          </a-button>
          <a-button :type="activeTab === 'ai' ? 'primary' : 'default'" @click="activeTab = 'ai'">
            <a-icon type="robot" /> {{ $t('aiStockScreener.aiMode') }}
          </a-button>
        </a-button-group>
      </div>
    </div>

    <div class="screener-body">
      <div class="left-panel">
        <div v-show="activeTab === 'filters'" class="filter-panel">
          <div class="panel-section">
            <div class="section-title">
              <a-icon type="database" /> {{ $t('aiStockScreener.universe') }}
            </div>
            <a-radio-group v-model="universeType" button-style="solid" class="universe-tabs">
              <a-radio-button value="hs300">沪深300</a-radio-button>
              <a-radio-button value="sz50">上证50</a-radio-button>
              <a-radio-button value="zz500">中证500</a-radio-button>
              <a-radio-button value="cyb">创业板</a-radio-button>
              <a-radio-button value="custom">{{ $t('aiStockScreener.custom') }}</a-radio-button>
            </a-radio-group>
          </div>

          <div class="panel-section">
            <div class="section-title">
              <a-icon type="bar-chart" /> {{ $t('aiStockScreener.fundamental') }}
            </div>
            <a-form layout="vertical">
              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item :label="$t('aiStockScreener.peRatio')">
                    <a-input-number v-model="filters.peMin" :min="0" :placeholder="'最低'" style="width: 100%;" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item :label="'—'">
                    <a-input-number v-model="filters.peMax" :min="0" :placeholder="'最高'" style="width: 100%;" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item :label="$t('aiStockScreener.pbRatio')">
                    <a-input-number v-model="filters.pbMin" :min="0" :placeholder="'最低'" style="width: 100%;" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item :label="'—'">
                    <a-input-number v-model="filters.pbMax" :min="0" :placeholder="'最高'" style="width: 100%;" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-form-item :label="$t('aiStockScreener.roe')">
                <a-slider v-model="filters.roeMin" :min="0" :max="50" :marks="roeMarks" />
              </a-form-item>
              <a-form-item :label="$t('aiStockScreener.revenueGrowth')">
                <a-slider v-model="filters.revenueGrowthMin" :min="-50" :max="100" :marks="revenueGrowthMarks" />
              </a-form-item>
            </a-form>
          </div>

          <div class="panel-section">
            <div class="section-title">
              <a-icon type="line-chart" /> {{ $t('aiStockScreener.technical') }}
            </div>
            <a-form layout="vertical">
              <a-form-item :label="$t('aiStockScreener.maFilter')">
                <a-checkbox v-model="filters.aboveMa20">股价在20日均线上方</a-checkbox>
                <a-checkbox v-model="filters.aboveMa60">股价在60日均线上方</a-checkbox>
                <a-checkbox v-model="filters.maBullish">均线多头排列</a-checkbox>
              </a-form-item>
              <a-form-item :label="$t('aiStockScreener.volumeFilter')">
                <a-checkbox v-model="filters.volumeSurged">放量上涨</a-checkbox>
                <a-checkbox v-model="filters.highTurnover">高换手率</a-checkbox>
              </a-form-item>
              <a-form-item :label="$t('aiStockScreener.changeFilter')">
                <a-slider v-model="filters.changeMin" :min="-10" :max="10" :step="0.5" :marks="changeMarks" />
              </a-form-item>
            </a-form>
          </div>

          <div class="panel-section">
            <div class="section-title">
              <a-icon type="apartment" /> {{ $t('aiStockScreener.sectorFilter') }}
            </div>
            <a-select
              v-model="filters.sectors"
              mode="multiple"
              :placeholder="$t('aiStockScreener.selectSectors')"
              style="width: 100%;"
            >
              <a-select-option v-for="sector in sectors" :key="sector" :value="sector">{{ sector }}</a-select-option>
            </a-select>
          </div>

          <div class="panel-actions">
            <a-button type="primary" block icon="search" :loading="screening" @click="runScreening">
              {{ $t('aiStockScreener.runScreen') }}
            </a-button>
            <a-button block icon="reload" style="margin-top: 8px;" @click="resetFilters">
              {{ $t('aiStockScreener.reset') }}
            </a-button>
          </div>
        </div>

        <div v-show="activeTab === 'ai'" class="ai-panel">
          <div class="ai-header">
            <div class="ai-icon">
              <a-icon type="robot" />
            </div>
            <div class="ai-title">
              <h3>{{ $t('aiStockScreener.aiScreener') }}</h3>
              <p>{{ $t('aiStockScreener.aiScreenerDesc') }}</p>
            </div>
          </div>

          <div class="quick-prompts">
            <div class="prompt-title">{{ $t('aiStockScreener.quickPrompts') }}</div>
            <a-row :gutter="8">
              <a-col :span="12" v-for="prompt in quickPrompts" :key="prompt.key">
                <a-button class="prompt-btn" block @click="applyPrompt(prompt)">
                  <a-icon :type="prompt.icon" />
                  <span>{{ prompt.label }}</span>
                </a-button>
              </a-col>
            </a-row>
          </div>

          <div class="ai-input-section">
            <a-textarea
              v-model="aiPrompt"
              :placeholder="$t('aiStockScreener.aiPlaceholder')"
              :rows="6"
              @keydown.ctrl.enter.exact="runAiScreening"
            />
            <div class="ai-input-actions">
              <span class="ai-hint">{{ $t('aiStockScreener.ctrlEnter') }}</span>
              <a-button type="primary" icon="thunderbolt" :loading="aiScreening" @click="runAiScreening">
                {{ $t('aiStockScreener.aiAnalyze') }}
              </a-button>
            </div>
          </div>

          <div v-if="aiResult" class="ai-result-panel">
            <div class="ai-result-header">
              <a-icon type="bulb" />
              <span>{{ $t('aiStockScreener.aiAnalysis') }}</span>
            </div>
            <div class="ai-result-content" v-html="renderMarkdown(aiResult.analysis)"></div>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <div class="results-header">
          <div class="results-stats">
            <span class="stat-item">
              <span class="stat-label">{{ $t('aiStockScreener.totalFound') }}</span>
              <span class="stat-value">{{ totalCount }}</span>
            </span>
            <span class="stat-divider">|</span>
            <span class="stat-item">
              <span class="stat-label">{{ $t('aiStockScreener.universe') }}</span>
              <span class="stat-value">{{ universeLabel }}</span>
            </span>
          </div>
          <div class="results-actions">
            <a-select v-model="sortBy" size="small" style="width: 140px;" @change="sortResults">
              <a-select-option value="score">{{ $t('aiStockScreener.sortByScore') }}</a-select-option>
              <a-select-option value="change">{{ $t('aiStockScreener.sortByChange') }}</a-select-option>
              <a-select-option value="volume">{{ $t('aiStockScreener.sortByVolume') }}</a-select-option>
              <a-select-option value="pe">{{ $t('aiStockScreener.sortByPE') }}</a-select-option>
            </a-select>
            <a-button size="small" icon="download" style="margin-left: 8px;">
              {{ $t('aiStockScreener.export') }}
            </a-button>
          </div>
        </div>

        <div class="results-table">
          <a-table
            :columns="columns"
            :data-source="sortedResults"
            :loading="screening || aiScreening"
            :pagination="paginationConfig"
            :row-key="rowKey"
            size="middle"
          >
            <template slot="rank" slot-scope="text, record, index">
              <span class="rank-badge" :class="'rank-' + (index + 1)">
                {{ index + 1 }}
              </span>
            </template>
            <template slot="symbol" slot-scope="text, record">
              <div class="symbol-cell">
                <span class="symbol-code">{{ record.symbol }}</span>
                <span class="symbol-name">{{ record.name }}</span>
              </div>
            </template>
            <template slot="change" slot-scope="text, record">
              <span class="change-value" :class="record.change >= 0 ? 'up' : 'down'">
                {{ record.change >= 0 ? '+' : '' }}{{ record.change.toFixed(2) }}%
              </span>
            </template>
            <template slot="score" slot-scope="text, record">
              <a-progress
                :percent="record.score"
                :stroke-color="getScoreColor(record.score)"
                :show-info="false"
                size="small"
              />
              <span class="score-text" :style="{ color: getScoreColor(record.score) }">{{ record.score }}</span>
            </template>
            <template slot="action" slot-scope="text, record">
              <a-button type="link" size="small" @click="viewDetail(record)">
                <a-icon type="eye" /> {{ $t('aiStockScreener.viewDetail') }}
              </a-button>
              <a-button type="link" size="small" @click="addToWatchlist(record)">
                <a-icon type="star" /> {{ $t('aiStockScreener.addWatchlist') }}
              </a-button>
            </template>
          </a-table>
        </div>
      </div>
    </div>

    <a-modal
      :visible="showDetail"
      :title="detailStock ? (detailStock.name + ' (' + detailStock.symbol + ')') : ''"
      @cancel="showDetail = false"
      :footer="null"
      width="900px"
      :wrapClassName="isDarkTheme ? 'qd-dark-modal' : ''"
    >
      <div v-if="detailStock" class="stock-detail-modal">
        <div class="detail-tabs">
          <a-tabs v-model="detailTab">
            <a-tab-pane :tab="$t('aiStockScreener.overview')" key="overview">
              <div class="detail-overview">
                <a-row :gutter="16">
                  <a-col :span="8">
                    <div class="info-card">
                      <div class="info-label">{{ $t('aiStockScreener.price') }}</div>
                      <div class="info-value">{{ detailStock.price }}</div>
                      <div class="info-change" :class="detailStock.change >= 0 ? 'up' : 'down'">
                        {{ detailStock.change >= 0 ? '+' : '' }}{{ detailStock.change.toFixed(2) }}%
                      </div>
                    </div>
                  </a-col>
                  <a-col :span="8">
                    <div class="info-card">
                      <div class="info-label">{{ $t('aiStockScreener.peRatio') }}</div>
                      <div class="info-value">{{ detailStock.pe || '--' }}</div>
                      <div class="info-sub">{{ $t('aiStockScreener.peRatio') }}</div>
                    </div>
                  </a-col>
                  <a-col :span="8">
                    <div class="info-card">
                      <div class="info-label">{{ $t('aiStockScreener.pbRatio') }}</div>
                      <div class="info-value">{{ detailStock.pb || '--' }}</div>
                      <div class="info-sub">{{ $t('aiStockScreener.pbRatio') }}</div>
                    </div>
                  </a-col>
                </a-row>
                <div style="margin-top: 16px;">
                  <h4>{{ $t('aiStockScreener.aiRecommendation') }}</h4>
                  <div class="ai-recommendation">
                    <a-alert
                      :message="detailStock.recommendation"
                      :type="detailStock.recommendationType"
                      show-icon
                    />
                  </div>
                </div>
              </div>
            </a-tab-pane>
            <a-tab-pane :tab="$t('aiStockScreener.fundamental')" key="fundamental">
              <div class="detail-fundamental">
                <a-descriptions bordered :column="2" size="small">
                  <a-descriptions-item :label="$t('aiStockScreener.peRatio')">{{ detailStock.pe || '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.pbRatio')">{{ detailStock.pb || '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.roe')">{{ detailStock.roe ? detailStock.roe + '%' : '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.marketCap')">{{ detailStock.marketCap || '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.revenue')">{{ detailStock.revenue || '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.revenueGrowth')">{{ detailStock.revenueGrowth ? detailStock.revenueGrowth + '%' : '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.netProfit')">{{ detailStock.netProfit || '--' }}</a-descriptions-item>
                  <a-descriptions-item :label="$t('aiStockScreener.profitGrowth')">{{ detailStock.profitGrowth ? detailStock.profitGrowth + '%' : '--' }}</a-descriptions-item>
                </a-descriptions>
              </div>
            </a-tab-pane>
            <a-tab-pane :tab="$t('aiStockScreener.technical')" key="technical">
              <div class="detail-technical">
                <a-descriptions bordered :column="2" size="small">
                  <a-descriptions-item label="MA5">{{ detailStock.ma5 || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="MA10">{{ detailStock.ma10 || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="MA20">{{ detailStock.ma20 || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="MA60">{{ detailStock.ma60 || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="RSI">{{ detailStock.rsi || '--' }}</a-descriptions-item>
                  <a-descriptions-item label="MACD">{{ detailStock.macd || '--' }}</a-descriptions-item>
                </a-descriptions>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
        <div class="detail-actions">
          <a-button type="primary" icon="thunderbolt" @click="analyzeStock(detailStock)">
            {{ $t('aiStockScreener.deepAnalysis') }}
          </a-button>
          <a-button icon="star" @click="addToWatchlist(detailStock)">
            {{ $t('aiStockScreener.addWatchlist') }}
          </a-button>
          <a-button icon="line-chart" @click="goToChart(detailStock)">
            {{ $t('aiStockScreener.viewChart') }}
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import { addWatchlist } from '@/api/market'
import { screenStocks, aiScreenStocks, getSectors } from '@/api/stock-screener'

export default {
  name: 'AIStockScreener',
  data () {
    return {
      activeTab: 'filters',
      universeType: 'hs300',
      sortBy: 'score',
      filters: {
        peMin: null,
        peMax: null,
        pbMin: null,
        pbMax: null,
        roeMin: 10,
        revenueGrowthMin: 0,
        aboveMa20: false,
        aboveMa60: false,
        maBullish: false,
        volumeSurged: false,
        highTurnover: false,
        changeMin: -10,
        sectors: []
      },
      sectors: [],
      results: [],
      totalCount: 0,
      screening: false,
      aiScreening: false,
      aiPrompt: '',
      aiResult: null,
      showDetail: false,
      detailStock: null,
      detailTab: 'overview',
      quickPrompts: [
        { key: 'value', label: '低估值蓝筹', icon: 'wallet', desc: 'PE<15, PB<2, ROE>15%' },
        { key: 'growth', label: '高成长股', icon: 'rocket', desc: '营收增长>30%, 净利润增长>25%' },
        { key: 'tech', label: '科技龙头', icon: 'api', desc: '半导体、AI、新能源等科技赛道' },
        { key: 'dividend', label: '高股息', icon: 'gold', desc: '股息率>4%, 连续5年分红' },
        { key: 'breakout', label: '突破型', icon: 'rise', desc: '放量突破平台, 均线多头排列' },
        { key: 'reversal', label: '超跌反弹', icon: 'fall', desc: '跌幅超50%, 底部放量企稳' },
      ]
    }
  },
  computed: {
    ...mapState({
      navTheme: state => state.app.theme,
      primaryColor: state => state.app.color || '#1890ff'
    }),
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    roeMarks () {
      return { 0: '0%', 10: '10%', 20: '20%', 30: '30%', 50: '50%' }
    },
    revenueGrowthMarks () {
      return { '-50': '-50%', 0: '0%', 20: '20%', 50: '50%', 100: '100%' }
    },
    changeMarks () {
      return { '-10': '-10%', '-5': '-5%', 0: '0%', 5: '5%', 10: '10%' }
    },
    paginationConfig () {
      return { pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }
    },
    universeLabel () {
      const map = {
        hs300: '沪深300',
        sz50: '上证50',
        zz500: '中证500',
        cyb: '创业板',
        custom: '自定义'
      }
      return map[this.universeType] || '沪深300'
    },
    sortedResults () {
      const list = [...this.results]
      switch (this.sortBy) {
        case 'change':
          return list.sort((a, b) => b.change - a.change)
        case 'volume':
          return list.sort((a, b) => parseFloat(b.volume) - parseFloat(a.volume))
        case 'pe':
          return list.sort((a, b) => (a.pe || 999) - (b.pe || 999))
        case 'score':
        default:
          return list.sort((a, b) => b.score - a.score)
      }
    },
    columns () {
      return [
        { title: '#', key: 'rank', scopedSlots: { customRender: 'rank' }, width: 60 },
        { title: this.$t('aiStockScreener.stock'), key: 'symbol', scopedSlots: { customRender: 'symbol' }, width: 160 },
        { title: this.$t('aiStockScreener.price'), dataIndex: 'price', key: 'price', width: 100 },
        { title: this.$t('aiStockScreener.change'), key: 'change', scopedSlots: { customRender: 'change' }, width: 100 },
        { title: this.$t('aiStockScreener.peRatio'), dataIndex: 'pe', key: 'pe', width: 80 },
        { title: this.$t('aiStockScreener.score'), key: 'score', scopedSlots: { customRender: 'score' }, width: 140 },
        { title: this.$t('aiStockScreener.sector'), dataIndex: 'sector', key: 'sector', width: 100 },
        { title: this.$t('aiStockScreener.action'), key: 'action', scopedSlots: { customRender: 'action' }, width: 160, fixed: 'right' },
      ]
    }
  },
  mounted () {
    this.loadSectors()
    this.loadInitialResults()
  },
  methods: {
    loadSectors () {
      getSectors().then(res => {
        if (res && res.data && res.data.data) {
          this.sectors = res.data.data
        }
      }).catch(() => {
        this.sectors = ['银行', '保险', '证券', '白酒', '医药', '新能源', '半导体', '人工智能', '房地产', '基建', '消费', '家电', '汽车', '有色金属', '煤炭', '石油']
      })
    },
    loadInitialResults () {
      this.runScreening()
    },
    runScreening () {
      this.screening = true
      screenStocks({
        universe: this.universeType,
        pe_min: this.filters.peMin,
        pe_max: this.filters.peMax,
        pb_min: this.filters.pbMin,
        pb_max: this.filters.pbMax,
        roe_min: this.filters.roeMin,
        revenue_growth_min: this.filters.revenueGrowthMin,
        above_ma20: this.filters.aboveMa20,
        above_ma60: this.filters.aboveMa60,
        ma_bullish: this.filters.maBullish,
        volume_surged: this.filters.volumeSurged,
        high_turnover: this.filters.highTurnover,
        change_min: this.filters.changeMin,
        sectors: this.filters.sectors
      }).then(res => {
        if (res && res.data && res.data.data) {
          this.results = res.data.data.stocks || []
          this.totalCount = res.data.data.total || 0
        }
      }).catch(err => {
        console.error('Screening error:', err)
        this.$message.error('选股失败，请稍后重试')
      }).finally(() => {
        this.screening = false
      })
    },
    resetFilters () {
      this.filters = {
        peMin: null,
        peMax: null,
        pbMin: null,
        pbMax: null,
        roeMin: 10,
        revenueGrowthMin: 0,
        aboveMa20: false,
        aboveMa60: false,
        maBullish: false,
        volumeSurged: false,
        highTurnover: false,
        changeMin: -10,
        sectors: []
      }
    },
    applyPrompt (prompt) {
      const promptMap = {
        value: '帮我筛选A股低估值蓝筹股，要求PE小于15倍，PB小于2，ROE大于15%，股息率高于3%',
        growth: '找出A股高成长股票，营收增长率超过30%，净利润增长率超过25%，行业景气度高',
        tech: '筛选科技龙头股，包括半导体、人工智能、新能源等赛道，具有核心技术壁垒',
        dividend: '推荐高股息率股票，连续5年以上分红，股息率大于4%，现金流稳定',
        breakout: '找出近期放量突破的股票，均线呈多头排列，成交量放大2倍以上',
        reversal: '筛选超跌反弹标的，前期跌幅超过50%，底部放量企稳，有反转迹象'
      }
      this.aiPrompt = promptMap[prompt.key] || ''
      this.activeTab = 'ai'
    },
    runAiScreening () {
      if (!this.aiPrompt.trim()) return
      this.aiScreening = true
      this.aiResult = null

      aiScreenStocks({
        prompt: this.aiPrompt
      }).then(res => {
        if (res && res.data && res.data.data) {
          this.aiResult = {
            analysis: res.data.data.analysis || ''
          }
          this.results = res.data.data.stocks || []
          this.totalCount = res.data.data.total || 0
        }
      }).catch(err => {
        console.error('AI screening error:', err)
        if (err.response && err.response.data && err.response.data.code === 'INSUFFICIENT_CREDITS') {
          this.$message.error('积分不足，请先充值')
        } else {
          this.$message.error('AI选股失败，请稍后重试')
        }
      }).finally(() => {
        this.aiScreening = false
      })
    },
    sortResults () {
    },
    rowKey (record) {
      return record.symbol
    },
    getScoreColor (score) {
      if (score >= 85) return '#52c41a'
      if (score >= 70) return '#1890ff'
      if (score >= 55) return '#faad14'
      return '#ff4d4f'
    },
    viewDetail (record) {
      this.detailStock = {
        ...record,
        recommendation: '综合评级：买入建议。公司基本面稳健，估值合理，技术面呈上升趋势。',
        recommendationType: 'success',
        ma5: 1680.50,
        ma10: 1675.20,
        ma20: 1660.80,
        ma60: 1620.30,
        rsi: 62.5,
        macd: '金叉',
        marketCap: '2.12万亿',
        revenue: '1265亿',
        revenueGrowth: 16.5,
        netProfit: '528亿',
        profitGrowth: 18.2
      }
      this.showDetail = true
    },
    addToWatchlist (stock) {
      addWatchlist({
        market: 'CNStock',
        symbol: stock.symbol
      }).then(() => {
        this.$message.success(`${stock.name} 已加入自选`)
      }).catch(() => {
        this.$message.error('加入自选失败')
      })
    },
    analyzeStock (stock) {
      this.$router.push({
        path: '/ai-analysis',
        query: { symbol: `CNStock:${stock.symbol}` }
      })
    },
    goToChart (stock) {
      this.$router.push({
        path: '/indicator-ide',
        query: { market: 'CNStock', symbol: stock.symbol }
      })
    },
    renderMarkdown (text) {
      if (!text) return ''
      return text
        .replace(/### (.*?)\n/g, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br/>')
        .replace(/^- /gm, '• ')
    }
  }
}
</script>

<style lang="less" scoped>
.ai-stock-screener {
  padding: 16px;
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: #f5f7fa;

  &.theme-dark {
    background: #141414;
    color: #fff;
  }
}

.screener-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 0 4px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .header-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 24px;
    }

    .header-text {
      .page-title {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
      }
      .page-subtitle {
        margin: 2px 0 0;
        font-size: 13px;
        color: #666;
      }
    }
  }
}

.screener-body {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.left-panel {
  width: 340px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #fff;
  border-radius: 8px;
  padding: 16px;

  .theme-dark & {
    background: #1f1f1f;
  }
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
  border-radius: 8px;

  .theme-dark & {
    background: #1f1f1f;
  }
}

.panel-section {
  margin-bottom: 20px;

  .section-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #333;
    display: flex;
    align-items: center;
    gap: 6px;

    .theme-dark & {
      color: #ddd;
    }
  }
}

.universe-tabs {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.panel-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;

  .theme-dark & {
    border-top-color: #333;
  }
}

.ai-panel {
  .ai-header {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;

    .ai-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 24px;
      flex-shrink: 0;
    }

    .ai-title {
      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
      }
      p {
        margin: 4px 0 0;
        font-size: 12px;
        color: #999;
        line-height: 1.4;
      }
    }
  }

  .quick-prompts {
    margin-bottom: 16px;

    .prompt-title {
      font-size: 13px;
      font-weight: 500;
      margin-bottom: 8px;
      color: #666;
    }

    .prompt-btn {
      margin-bottom: 8px;
      text-align: left;
      height: auto;
      padding: 8px 12px;

      .anticon {
        margin-right: 6px;
      }

      span {
        font-size: 12px;
      }
    }
  }

  .ai-input-section {
    .ai-input-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 8px;

      .ai-hint {
        font-size: 12px;
        color: #999;
      }
    }
  }

  .ai-result-panel {
    margin-top: 16px;
    padding: 12px;
    background: #f6ffed;
    border-radius: 6px;
    border: 1px solid #b7eb8f;

    .theme-dark & {
      background: rgba(82, 196, 26, 0.1);
      border-color: rgba(82, 196, 26, 0.3);
    }

    .ai-result-header {
      font-weight: 600;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
      color: #389e0d;
    }

    .ai-result-content {
      font-size: 13px;
      line-height: 1.6;
      color: #333;

      .theme-dark & {
        color: #ddd;
      }

      h3 {
        margin: 8px 0 4px;
        font-size: 14px;
      }

      strong {
        color: #1890ff;
      }
    }
  }
}

.results-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .theme-dark & {
    border-bottom-color: #333;
  }

  .results-stats {
    display: flex;
    align-items: center;
    gap: 12px;

    .stat-item {
      display: flex;
      flex-direction: column;
      gap: 2px;

      .stat-label {
        font-size: 12px;
        color: #999;
      }

      .stat-value {
        font-size: 18px;
        font-weight: 600;
        color: #1890ff;
      }
    }

    .stat-divider {
      color: #ddd;

      .theme-dark & {
        color: #444;
      }
    }
  }

  .results-actions {
    display: flex;
    align-items: center;
  }
}

.results-table {
  flex: 1;
  padding: 12px 16px;
  overflow: auto;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  background: #f0f0f0;
  color: #666;

  &.rank-1 { background: #ffd700; color: #fff; }
  &.rank-2 { background: #c0c0c0; color: #fff; }
  &.rank-3 { background: #cd7f32; color: #fff; }
}

.symbol-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .symbol-code {
    font-weight: 600;
    font-size: 13px;
  }

  .symbol-name {
    font-size: 12px;
    color: #999;
  }
}

.change-value {
  font-weight: 600;

  &.up { color: #52c41a; }
  &.down { color: #ff4d4f; }
}

.score-text {
  margin-left: 8px;
  font-weight: 600;
  font-size: 12px;
}

.stock-detail-modal {
  .detail-tabs {
    margin-bottom: 16px;
  }

  .detail-overview {
    .info-card {
      text-align: center;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;

      .theme-dark & {
        background: #2a2a2a;
      }

      .info-label {
        font-size: 12px;
        color: #999;
        margin-bottom: 4px;
      }

      .info-value {
        font-size: 24px;
        font-weight: 600;
        color: #333;

        .theme-dark & {
          color: #fff;
        }
      }

      .info-change {
        font-size: 13px;
        margin-top: 2px;
        font-weight: 500;

        &.up { color: #52c41a; }
        &.down { color: #ff4d4f; }
      }

      .info-sub {
        font-size: 11px;
        color: #bbb;
        margin-top: 2px;
      }
    }

    .ai-recommendation {
      margin-top: 12px;
    }
  }

  .detail-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;

    .theme-dark & {
      border-top-color: #333;
    }
  }
}
</style>
