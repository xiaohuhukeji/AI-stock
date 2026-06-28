<template>
  <div class="kronos-container">
    <a-card :bordered="false" class="search-card">
      <a-form :form="form" layout="inline" @submit.prevent="handlePredict">
        <a-form-item label="模型">
          <a-select v-model="formData.model" style="width: 220px" placeholder="选择模型" @change="handleModelChange">
            <a-select-option v-for="m in modelList" :key="m.name" :value="m.name">
              <span>{{ m.name }}</span>
              <span style="color: #999; margin-left: 8px; font-size: 12px">{{ m.params }}</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="市场">
          <a-select v-model="formData.market" style="width: 100px" placeholder="选择市场">
            <a-select-option value="CNStock">A股</a-select-option>
            <a-select-option value="USStock">美股</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="股票">
          <a-select
            v-model="formData.symbol"
            style="width: 200px"
            placeholder="选择自选股或输入代码"
            allow-clear
            show-search
            :filter-option="filterOption"
          >
            <a-select-option v-for="item in watchlistData" :key="item.symbol" :value="item.symbol">
              <span>{{ item.symbol }}</span>
              <span style="color: #999; margin-left: 8px; font-size: 12px">{{ item.name }}</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="历史天数">
          <a-input
            v-model="formData.lookback"
            type="number"
            style="width: 100px"
            placeholder="60-512"
          />
          <a-space :size="4" style="margin-left: 8px">
            <a-tag @click="formData.lookback = 200" style="cursor: pointer" color="blue">200</a-tag>
            <a-tag @click="formData.lookback = 400" style="cursor: pointer" color="blue">400</a-tag>
            <a-tag @click="formData.lookback = 512" style="cursor: pointer" color="blue">512</a-tag>
          </a-space>
        </a-form-item>
        <a-form-item label="预测天数">
          <a-input
            v-model="formData.pred_len"
            type="number"
            style="width: 100px"
            placeholder="1-240"
          />
          <a-space :size="4" style="margin-left: 8px">
            <a-tag @click="formData.pred_len = 60" style="cursor: pointer" color="green">60</a-tag>
            <a-tag @click="formData.pred_len = 120" style="cursor: pointer" color="green">120</a-tag>
            <a-tag @click="formData.pred_len = 240" style="cursor: pointer" color="green">240</a-tag>
          </a-space>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handlePredict" :loading="loading">
            <a-icon type="play-circle" /> 开始预测
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card :bordered="false" class="result-card" v-if="result">
      <template #title>
        <span class="result-title">
          <a-icon type="line-chart" /> Kronos AI 价格预测
        </span>
        <a-tag :color="result.up_or_down === 'up' ? 'green' : 'red'" style="margin-left: 10px">
          {{ result.up_or_down === 'up' ? '上涨预测' : '下跌预测' }}
        </a-tag>
      </template>

      <div class="stats-row">
        <a-statistic title="当前价格" :value="result.current_price" precision="2" />
        <a-statistic title="预测最高" :value="result.max_pred_price" precision="2" :value-style="{ color: '#52c41a' }" />
        <a-statistic title="预测最低" :value="result.min_pred_price" precision="2" :value-style="{ color: '#f5222d' }" />
        <a-statistic title="预测收盘" :value="result.last_pred_price" precision="2" :value-style="{ color: result.up_or_down === 'up' ? '#52c41a' : '#f5222d' }" />
      </div>

      <div class="chart-container">
        <div ref="chartRef" class="chart"></div>
      </div>

      <div class="result-info">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="预测周期">{{ result.pred_len }} 个交易日</a-descriptions-item>
          <a-descriptions-item label="数据点">历史 {{ result.actual_points }} + 预测 {{ result.predicted_points }}</a-descriptions-item>
          <a-descriptions-item label="预测模型">{{ currentModelName || '--' }}</a-descriptions-item>
          <a-descriptions-item label="预测时间">{{ result.predict_time }}</a-descriptions-item>
        </a-descriptions>
      </div>
    </a-card>

    <a-card :bordered="false" class="health-card">
      <template #title>
        <span>模型状态</span>
        <a-tag :color="healthStatus ? 'green' : 'red'" style="margin-left: 10px">
          {{ healthStatus ? '正常' : '异常' }}
        </a-tag>
      </template>
      <div class="health-info" v-if="healthStatus">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="模型名称">{{ healthData.model_name || '--' }}</a-descriptions-item>
          <a-descriptions-item label="运行设备">{{ healthData.device || '--' }}</a-descriptions-item>
          <a-descriptions-item label="上下文长度">{{ healthData.max_context || '--' }}</a-descriptions-item>
          <a-descriptions-item label="模型状态">{{ healthData.status || '--' }}</a-descriptions-item>
        </a-descriptions>
      </div>
      <div v-else>
        <a-empty description="模型服务未启动" />
      </div>
    </a-card>
  </div>
</template>

<script>
import { kronosPredict, kronosHealth, kronosModels, kronosLoadModel } from '@/api/kronos'
import { getWatchlist } from '@/api/market'
import * as echarts from 'echarts'

export default {
  name: 'KronosPredict',
  data () {
    return {
      form: this.$form.createForm(this),
      formData: {
        model: 'Kronos-small',
        market: 'CNStock',
        symbol: '',
        lookback: 400,
        pred_len: 120
      },
      modelList: [],
      watchlistData: [],
      loading: false,
      modelLoading: false,
      result: null,
      healthStatus: false,
      healthData: {},
      chartInstance: null,
      currentModelName: ''
    }
  },
  mounted () {
    this.loadModels()
    this.loadWatchlist()
    this.checkHealth()
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy () {
    if (this.chartInstance) {
      this.chartInstance.dispose()
    }
    window.removeEventListener('resize', this.handleResize)
  },
  methods: {
    filterOption (input, option) {
      return option.value.toLowerCase().indexOf(input.toLowerCase()) >= 0 ||
             (option.children && option.children[1] &&
              option.children[1].text.toLowerCase().indexOf(input.toLowerCase()) >= 0)
    },
    async loadWatchlist () {
      try {
        const res = await getWatchlist()
        const list = Array.isArray(res.data) ? res.data : ((res.data && res.data.watchlist) || [])
        this.watchlistData = list.map(item => ({
          symbol: item.symbol,
          name: item.name || item.symbol,
          market: item.market
        }))
      } catch (e) {
        this.watchlistData = []
      }
    },
    async loadModels () {
      try {
        const res = await kronosModels()
        if (res.code === 0 && res.data) {
          this.modelList = res.data.models || []
          if (res.data.current_model) {
            const cur = this.modelList.find(m => m.model_id === res.data.current_model)
            if (cur) {
              this.formData.model = cur.name
              this.currentModelName = cur.name
            }
          }
        }
      } catch (e) {
        this.modelList = [
          { name: 'Kronos-mini', params: '410万参数', description: '轻量模型' },
          { name: 'Kronos-small', params: '2470万参数', description: '小型模型' },
          { name: 'Kronos-base', params: '1.023亿参数', description: '基础模型' }
        ]
      }
    },
    async handleModelChange (modelName) {
      this.modelLoading = true
      try {
        const res = await kronosLoadModel(modelName)
        if (res.code === 0) {
          this.$message.success('模型 ' + modelName + ' 加载成功')
          this.currentModelName = modelName
          this.checkHealth()
        } else {
          this.$message.error(res.message || '模型加载失败')
        }
      } catch (e) {
        const msg = e.backendMessage || e.message || '模型加载失败'
        this.$message.error(msg)
      } finally {
        this.modelLoading = false
      }
    },
    async checkHealth () {
      try {
        const res = await kronosHealth()
        if (res.code === 0) {
          this.healthStatus = true
          this.healthData = res.data
        }
      } catch (e) {
        this.healthStatus = false
      }
    },
    async handlePredict () {
      if (!this.formData.symbol) {
        this.$message.warning('请选择或输入股票代码')
        return
      }
      this.loading = true
      this.result = null
      try {
        const res = await kronosPredict(this.formData)
        if (res.code === 0) {
          this.result = res.data
          this.currentModelName = this.formData.model
          this.$nextTick(() => {
            this.renderChart()
          })
        } else {
          this.$message.error(res.message || '预测失败')
        }
      } catch (e) {
        const msg = e.backendMessage || e.message || '预测失败，请检查网络连接'
        this.$message.error(msg)
      } finally {
        this.loading = false
      }
    },
    renderChart () {
      if (!this.result || !this.result.predictions) return
      if (this.chartInstance) {
        this.chartInstance.dispose()
      }
      const actualData = this.result.predictions.filter(p => p.type === 'actual')
      const predData = this.result.predictions.filter(p => p.type === 'prediction')
      const dates = [...actualData.map(p => p.date), ...predData.map(p => p.date)].map(d => {
        if (typeof d === 'string') {
          if (d.includes('T')) {
            const parts = d.split('T')
            return parts[0] || 'N/A'
          }
          return d
        }
        return 'N/A'
      })
      const actualPrices = actualData.map(p => p.close)
      const predPrices = new Array(actualData.length).fill(null).concat(predData.map(p => p.close))
      const predHigh = new Array(actualData.length).fill(null).concat(predData.map(p => p.high))
      const predLow = new Array(actualData.length).fill(null).concat(predData.map(p => p.low))
      const dom = this.$refs.chartRef
      if (!dom) return
      this.chartInstance = echarts.init(dom)
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' }
        },
        legend: {
          data: ['历史价格', '预测价格', '预测区间']
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '8%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: {
            rotate: 45,
            fontSize: 10,
            interval: 'auto',
            formatter: function(value, index) {
              if (typeof value === 'string' && value.length > 10) {
                return value.substring(5)
              }
              return value
            }
          },
          axisTick: {
            alignWithLabel: true,
            interval: 'auto'
          }
        },
        dataZoom: [
          {
            type: 'inside',
            start: 0,
            end: 100
          }
        ],
        yAxis: {
          type: 'value',
          scale: true
        },
        series: [
          {
            name: '历史价格',
            type: 'line',
            data: actualPrices,
            smooth: true,
            lineStyle: { color: '#1890ff', width: 2 },
            showSymbol: false
          },
          {
            name: '预测价格',
            type: 'line',
            data: predPrices,
            smooth: true,
            lineStyle: { color: '#52c41a', width: 2, type: 'dashed' },
            showSymbol: false
          },
          {
            name: '预测区间',
            type: 'line',
            data: predLow,
            itemStyle: { color: 'rgba(255, 193, 7, 0.1)' },
            lineStyle: { color: '#ffc107', width: 1, type: 'dashed' },
            showSymbol: false,
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(255, 193, 7, 0.3)' },
                { offset: 1, color: 'rgba(255, 193, 7, 0.05)' }
              ])
            }
          },
          {
            name: '预测区间',
            type: 'line',
            data: predHigh,
            itemStyle: { color: '#ffc107' },
            lineStyle: { color: '#ffc107', width: 1, type: 'dashed' },
            showSymbol: false,
            areaStyle: {}
          }
        ]
      }
      this.chartInstance.setOption(option)
    },
    handleResize () {
      if (this.chartInstance) {
        this.chartInstance.resize()
      }
    }
  }
}
</script>

<style scoped>
.kronos-container {
  padding: 24px;
  background: #f0f2f5;
  min-height: calc(100vh - 64px);
}

.search-card {
  margin-bottom: 24px;
}

.result-card {
  margin-bottom: 24px;
}

.result-title {
  font-size: 16px;
  font-weight: bold;
}

.stats-row {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.chart-container {
  margin-bottom: 24px;
}

.chart {
  width: 100%;
  height: 400px;
}

.result-info {
  margin-top: 16px;
}

.health-card {
  margin-bottom: 24px;
}

.health-info {
  margin-top: 16px;
}
</style>
