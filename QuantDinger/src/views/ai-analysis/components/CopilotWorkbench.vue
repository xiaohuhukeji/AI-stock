<template>
  <div class="copilot-workbench">
    <aside class="left-rail">
      <section class="rail-panel sessions-panel">
        <div class="panel-head">
          <span><a-icon type="history" /> {{ text.sessions }}</span>
          <a-button size="small" type="link" @click="newSession">{{ text.newChat }}</a-button>
        </div>
        <div v-if="sessions.length === 0" class="empty-mini">{{ text.noSessions }}</div>
        <div v-else class="session-list">
          <div
            v-for="session in sessions.slice(0, 30)"
            :key="session.id"
            class="session-row"
            :class="{ active: session.id === sessionId }"
          >
            <button type="button" class="session-card" @click="loadHistory(session.id)">
              <strong>{{ session.title || text.untitled }}</strong>
              <span>{{ session.context_symbol || session.context_market || text.chatSession }}<span v-if="session.context_name" class="session-name">({{ session.context_name }})</span></span>
            </button>
            <a-popconfirm
              :title="text.deleteSessionConfirm"
              :ok-text="text.remove"
              :cancel-text="text.cancel"
              @confirm="removeSession(session)"
            >
              <a-tooltip :title="text.remove">
                <button type="button" class="session-delete" @click.stop><a-icon type="delete" /></button>
              </a-tooltip>
            </a-popconfirm>
          </div>
        </div>
      </section>

    </aside>

    <main class="chat-panel">
      <header class="chat-hero">
        <div class="hero-main">
          <div class="hero-copy">
            <span class="eyebrow">AI Copilot</span>
            <p>{{ text.subtitle }}</p>
          </div>
          <div class="context-bar">
            <div class="context-status">
              <a-icon type="database" />
              <span>{{ text.focusSymbol }}</span>
              <strong>{{ currentContextLabel }}</strong>
            </div>
            <div class="symbol-picker hero-symbol-picker">
              <a-select
                ref="contextSymbolSelect"
                v-model="selectedSymbolValue"
                show-search
                allow-clear
                size="large"
                dropdown-class-name="copilot-symbol-dropdown"
                :placeholder="text.symbolPlaceholder"
                :filter-option="false"
                :not-found-content="symbolSearching ? undefined : text.noSymbol"
                @focus="seedSymbolOptions"
                @search="handleSymbolSearch"
                @change="handleSymbolChange"
              >
                <a-spin v-if="symbolSearching" slot="notFoundContent" size="small" />
                <a-select-option
                  v-for="item in selectableSymbols"
                  :key="symbolOptionValue(item)"
                  :value="symbolOptionValue(item)"
                >
                  <div class="symbol-option">
                    <strong>{{ item.symbol }}</strong>
                    <span>{{ item.name || item.market }}</span>
                    <em :class="['symbol-market-pill', marketPillClass(item.market)]">{{ marketLabel(item.market) }}</em>
                  </div>
                </a-select-option>
              </a-select>
            </div>
          </div>
        </div>
      </header>

      <div ref="messages" class="messages">
        <div v-if="messages.length === 0" class="welcome">
          <a-icon type="robot" />
          <h3>{{ text.welcomeTitle }}</h3>
          <p>{{ text.welcomeDesc }}</p>
          <div class="welcome-prompts">
            <button
              v-for="item in registeredQuickTasks"
              :key="'welcome-' + item.key"
              type="button"
              :class="['welcome-task', item.tone ? `welcome-task--${item.tone}` : '']"
              @click="handleQuickPrompt(item)"
            >
              <span class="task-icon"><a-icon :type="item.icon" /></span>
              <span class="task-copy">
                <strong>{{ item.label }}</strong>
                <em>{{ item.desc }}</em>
              </span>
            </button>
          </div>
        </div>

        <article
          v-for="msg in messages"
          :key="msg.localId || msg.id"
          class="message"
          :class="[
            msg.role,
            {
              'report-message': msg.report || msg.reportLoading || msg.reportError,
              'printing-report-message': printReportId && reportId(msg) === printReportId,
              'thinking-message': msg.isThinking
            }
          ]"
        >
          <div class="avatar">
            <a-icon :type="msg.role === 'assistant' ? 'robot' : 'user'" />
          </div>
          <div class="bubble">
            <div v-if="msg.attachments && msg.attachments.length" class="attachment-row">
              <div v-for="att in msg.attachments" :key="att.name" class="thumb">
                <img :src="att.data_url || att.preview" :alt="att.name">
              </div>
            </div>
            <div class="message-content" v-html="renderMarkdown(msg.content)" @click="handleMessageContentClick" />
            <div
              v-if="msg.report || msg.reportLoading || msg.reportError"
              :data-report-id="reportId(msg)"
              class="copilot-report-card"
            >
              <FastAnalysisReport
                :result="msg.report || null"
                :loading="!!msg.reportLoading"
                :error="msg.reportError || null"
                :error-tone="msg.reportErrorTone || 'error'"
                @retry="retryProfessionalAnalysis(msg)"
                @generate-strategy="handleReportGenerateStrategy"
                @go-backtest="handleReportGoBacktest"
              />
            </div>
            <div v-if="msg.meta" class="message-meta">{{ msg.meta }}</div>
            <div v-if="visibleMessageActions(msg).length || strategyCodeForMessage(msg)" class="message-actions">
              <button v-for="action in visibleMessageActions(msg)" :key="action.key || action.label" type="button" @click="runMessageAction(action)">
                <a-icon :type="action.icon || 'arrow-right'" /> {{ action.label }}
              </button>
              <button v-if="strategyCodeForMessage(msg)" type="button" @click="copyStrategyCode(msg)">
                <a-icon type="copy" /> {{ isZh ? '复制代码' : 'Copy code' }}
              </button>
            </div>
            <div v-if="formatMessageTime(msg)" class="message-time">{{ formatMessageTime(msg) }}</div>
          </div>
        </article>
      </div>

      <div v-if="attachments.length" class="pending-attachments">
        <div v-for="(att, idx) in attachments" :key="att.name + idx" class="pending-thumb">
          <img :src="att.data_url" :alt="att.name">
          <button type="button" @click="removeAttachment(idx)"><a-icon type="close" /></button>
        </div>
      </div>

      <footer class="composer">
        <textarea
          ref="composerInput"
          v-model="draft"
          :placeholder="text.placeholder"
          :style="{ height: composerHeight + 'px' }"
          @input="resizeComposer"
          @keydown.enter.exact.prevent="sendMessage"
          @keydown.ctrl.enter.prevent="sendMessage"
          @keydown.meta.enter.prevent="sendMessage"
          @paste="handlePaste"
        />
        <div class="composer-foot">
          <p class="risk-disclaimer">
            <a-icon type="safety-certificate" />
            {{ text.riskDisclaimer || (isZh ? 'AI 回答仅供参考，不构成投资建议；市场有风险，交易需谨慎。' : 'AI responses are for reference only and do not constitute investment advice. Markets involve risk.') }}
          </p>
          <div class="composer-actions">
            <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" multiple @change="handleFiles">
            <a-button @click="$refs.fileInput.click()">
              <a-icon type="picture" /> {{ uploadImageLabel }}
            </a-button>
            <a-button type="primary" :loading="sending" :disabled="!canSend" @click="sendMessage">
              <a-icon type="thunderbolt" /> {{ text.send }}
            </a-button>
          </div>
        </div>
      </footer>
    </main>

    <aside class="right-rail">
      <section class="rail-panel watch-panel">
        <div class="panel-head">
          <span><a-icon type="star" theme="filled" /> {{ text.watchlist }}</span>
          <a-button size="small" type="link" @click="loadWatchlist"><a-icon type="reload" /></a-button>
        </div>
        <div class="add-watch">
          <a-button type="primary" block icon="plus" @click="openAddWatchModal">{{ text.addWatch }}</a-button>
        </div>
        <div v-if="watchlist.length === 0" class="empty-mini">{{ text.noWatchlist }}</div>
        <div v-else class="watch-list">
          <div
            v-for="item in watchlist.slice(0, 12)"
            :key="watchKey(item)"
            class="watch-card"
            :class="{ active: watchKey(item) === selectedSymbolValue }"
          >
            <button type="button" class="watch-main" @click="selectWatch(item)">
              <span class="watch-identity">
                <strong>{{ item.symbol }}</strong>
                <em>{{ item.name || marketLabel(item.market) }}</em>
              </span>
              <span class="watch-market-data">
                <strong class="watch-price">{{ formatPriceValue(priceFor(item) && priceFor(item).price) }}</strong>
                <em :class="watchChangeClass(item)" class="watch-change">
                  {{ formatChangePercent(priceFor(item)) }}
                </em>
              </span>
            </button>
            <div class="watch-actions">
              <a-tooltip :title="text.ask">
                <button type="button" @click="askWatch(item)"><a-icon type="message" /></button>
              </a-tooltip>
              <a-tooltip :title="text.schedule">
                <button type="button" @click="openTaskModal(item)"><a-icon type="clock-circle" /></button>
              </a-tooltip>
              <a-popconfirm
                :title="text.removeWatchConfirm"
                :ok-text="text.remove"
                :cancel-text="text.cancel"
                @confirm="removeWatch(item)"
              >
                <a-tooltip :title="text.remove">
                  <button type="button" class="danger" @click.stop><a-icon type="delete" /></button>
                </a-tooltip>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </section>

      <section class="rail-panel monitor-panel">
        <div class="panel-head">
          <span><a-icon type="clock-circle" /> {{ text.monitors }}</span>
          <a-button size="small" type="link" :loading="loadingMonitors" @click="loadMonitors"><a-icon type="reload" /></a-button>
        </div>
        <div v-if="monitors.length === 0" class="empty-mini">{{ text.noMonitors }}</div>
        <div v-else class="monitor-list">
          <div v-for="m in monitors.slice(0, 8)" :key="m.id" class="monitor-card">
            <div>
              <strong>{{ monitorSymbol(m) }}</strong>
              <span>{{ intervalText(m) }} · {{ m.is_active ? text.running : text.paused }}</span>
            </div>
            <div class="monitor-actions">
              <button type="button" @click="toggleMonitor(m)"><a-icon :type="m.is_active ? 'pause' : 'caret-right'" /></button>
              <button type="button" @click="removeMonitor(m)"><a-icon type="delete" /></button>
            </div>
          </div>
        </div>
      </section>
    </aside>

    <a-modal
      v-model="eventModalVisible"
      :title="text.eventDetail"
      :footer="null"
      wrap-class-name="copilot-modal"
      width="680px"
    >
      <div v-if="selectedEvent" class="event-detail">
        <div class="event-title-row">
          <div>
            <strong>{{ eventTitle(selectedEvent) }}</strong>
            <span>{{ formatEventTime(selectedEvent) }} · {{ selectedEvent.country || selectedEvent.region || '--' }}</span>
          </div>
          <em :class="['impact-pill', impactClass(selectedEvent)]">{{ impactLabel(selectedEvent) }}</em>
        </div>
        <div class="event-fields">
          <div><label>{{ text.actual }}</label><strong>{{ selectedEvent.actual || selectedEvent.value || '--' }}</strong></div>
          <div><label>{{ text.forecast }}</label><strong>{{ selectedEvent.forecast || selectedEvent.consensus || '--' }}</strong></div>
          <div><label>{{ text.previous }}</label><strong>{{ selectedEvent.previous || '--' }}</strong></div>
        </div>
        <section class="event-ai-preview">
          <h4><a-icon type="thunderbolt" /> {{ text.aiPreview }}</h4>
          <p>{{ eventPreview(selectedEvent) }}</p>
        </section>
        <div class="modal-actions">
          <a-button @click="eventModalVisible = false">{{ text.close }}</a-button>
          <a-button type="primary" @click="askAboutEvent(selectedEvent, true)">
            <a-icon type="message" /> {{ text.askAiEvent }}
          </a-button>
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model="taskModalVisible"
      :title="text.createMonitor"
      :ok-text="text.save"
      :cancel-text="text.cancel"
      :confirm-loading="savingMonitor"
      wrap-class-name="copilot-modal"
      @ok="saveMonitor"
    >
      <a-form layout="vertical">
        <a-form-item :label="text.symbol">
          <a-input :value="taskSymbolLabel" disabled />
        </a-form-item>
        <a-form-item :label="text.interval">
          <a-select v-model="taskForm.interval_min">
            <a-select-option :value="60">1h</a-select-option>
            <a-select-option :value="240">4h</a-select-option>
            <a-select-option :value="720">12h</a-select-option>
            <a-select-option :value="1440">1d</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="text.notify">
          <a-checkbox-group v-model="taskForm.notify_channels">
            <a-checkbox value="browser">Browser</a-checkbox>
            <a-checkbox value="email">Email</a-checkbox>
            <a-checkbox value="telegram">Telegram</a-checkbox>
          </a-checkbox-group>
        </a-form-item>
        <a-alert :message="text.monitorTip" type="info" show-icon />
      </a-form>
    </a-modal>

    <a-modal
      v-model="addWatchModalVisible"
      :title="text.addWatchTitle"
      :ok-text="text.add"
      :cancel-text="text.cancel"
      :confirm-loading="addingWatch"
      :ok-button-props="{ props: { disabled: !addWatchSelected } }"
      wrap-class-name="copilot-modal add-watch-copilot-modal"
      width="620px"
      @ok="confirmAddWatchSymbol"
      @cancel="closeAddWatchModal"
    >
      <div class="add-watch-modal">
        <a-tabs v-model="addWatchMarket" @change="handleAddWatchMarketChange">
          <a-tab-pane v-for="market in markets" :key="market.value" :tab="marketLabel(market.value)" />
        </a-tabs>
        <a-input-search
          v-model="addWatchKeyword"
          size="large"
          allow-clear
          :loading="addWatchSearching"
          :placeholder="text.addWatchSearchPlaceholder"
          @search="searchAddWatchSymbols"
          @change="handleAddWatchKeywordChange"
        >
          <a-button slot="enterButton" type="primary" icon="search">{{ text.search }}</a-button>
        </a-input-search>

        <div class="add-watch-results">
          <div v-if="addWatchSearching" class="empty-mini">{{ text.loading }}</div>
          <div v-else-if="addWatchResults.length === 0" class="empty-mini">{{ text.addWatchEmptyHint }}</div>
          <template v-else>
            <button
              v-for="item in addWatchResults"
              :key="'modal-' + symbolOptionValue(item)"
              type="button"
              class="symbol-result-card"
              :class="{ active: addWatchSelected && symbolOptionValue(addWatchSelected) === symbolOptionValue(item) }"
              @click="selectAddWatchSymbol(item)"
            >
              <span>
                <strong>{{ item.symbol }}</strong>
                <em>{{ item.name || marketLabel(item.market) }}</em>
              </span>
              <em :class="['symbol-market-pill', marketPillClass(item.market)]">{{ marketLabel(item.market) }}</em>
            </button>
          </template>
        </div>

        <a-alert
          v-if="addWatchSelected"
          class="selected-watch-alert"
          type="info"
          show-icon
          :message="`${text.selected}: ${addWatchSelected.symbol}`"
          :description="addWatchSelected.name || marketLabel(addWatchSelected.market)"
        />
      </div>
    </a-modal>

    <a-modal
      v-model="strategyFlowVisible"
      :title="text.strategyFlowTitle"
      :footer="null"
      wrap-class-name="copilot-modal"
      width="720px"
    >
      <div class="strategy-flow">
        <div class="strategy-flow-guide">
          <span><a-icon type="edit" /> {{ isZh ? '描述想法' : 'Describe' }}</span>
          <span><a-icon type="code" /> {{ isZh ? '生成草稿' : 'Draft' }}</span>
          <span><a-icon type="experiment" /> {{ isZh ? '回测验证' : 'Backtest' }}</span>
          <span><a-icon type="rocket" /> {{ isZh ? '手动启用' : 'Manual launch' }}</span>
        </div>
        <button
          v-for="item in strategyTargets"
          :key="item.key"
          type="button"
          class="strategy-flow-card"
          @click="startStrategyFlow(item.key)"
        >
          <a-icon :type="item.icon" />
          <span>
            <strong>{{ item.title }}</strong>
            <em>{{ item.desc }}</em>
          </span>
        </button>
      </div>
    </a-modal>
  </div>
</template>

<script>
import {
  chatMessage,
  getChatHistory,
  getChatSessions,
  deleteChatSession,
  getWatchlist,
  getWatchlistPrices,
  addWatchlist,
  removeWatchlist,
  searchSymbols,
  getHotSymbols,
  getAgentPreflight,
  classifyAgentIntent,
  getAiSkills,
  getAiSkillPrompt,
  getUserMemory,
  saveUserMemory,
  saveCopilotMessage,
  exportChatReportPdf
} from '@/api/market'
import { aiGenerateStrategy } from '@/api/strategy'
import { getEconomicCalendar } from '@/api/global-market'
import { getMembershipPlans } from '@/api/billing'
import { getMonitors, addMonitor, updateMonitor, deleteMonitor } from '@/api/portfolio'
import { fastAnalyze } from '@/api/fast-analysis'
import storage from 'store'
import { ACCESS_TOKEN } from '@/store/mutation-types'
import { loadEnabledMarketOptions, firstMarketValue } from '@/utils/marketModules'
import FastAnalysisReport from './FastAnalysisReport.vue'

let localId = 1

export default {
  name: 'CopilotWorkbench',
  components: {
    FastAnalysisReport
  },
  data () {
    return {
      markets: [],
      context: { market: '', symbol: '' },
      selectedSymbolValue: '',
      watchAddValue: undefined,
      symbolOptions: [],
      symbolSearching: false,
      symbolSearchTimer: null,
      draft: '',
      attachments: [],
      messages: [],
      sessions: [],
      sessionId: null,
      sending: false,
      lastSendSignature: '',
      lastSendAt: 0,
      billing: { feature_costs: {} },
      calendarEvents: [],
      calendarFilter: 'high',
      calendarError: '',
      loadingCalendar: false,
      selectedEvent: null,
      eventModalVisible: false,
      watchlist: [],
      watchlistPrices: {},
      addWatchModalVisible: false,
      addingWatch: false,
      addWatchMarket: 'Crypto',
      addWatchKeyword: '',
      addWatchResults: [],
      addWatchSelected: null,
      addWatchSearching: false,
      addWatchSearchTimer: null,
      monitors: [],
      loadingMonitors: false,
      analyzingSymbol: false,
      strategyFlowVisible: false,
      generatingStrategy: false,
      pendingAgentTask: null,
      agentPreflight: null,
      skillRegistry: [],
      loadingSkills: false,
      userMemories: [],
      taskModalVisible: false,
      savingMonitor: false,
      taskTarget: null,
      taskForm: { interval_min: 240, notify_channels: [] },
      composerHeight: 98,
      composerMinHeight: 98,
      composerMaxHeight: 236,
      draftContextLock: null,
      printReportId: ''
    }
  },
  computed: {
    isZh () {
      const locale = this.$i18n ? String(this.$i18n.locale || '') : 'zh-CN'
      return locale.toLowerCase().startsWith('zh')
    },
    text () {
      if (this.isZh) {
        return {
          title: 'AI 交易 Copilot',
          subtitle: '搜索标的、查看事件、分析行情、诊断策略和生成代码，都从这里发起。',
          sessions: '会话历史',
          newChat: '新会话',
          noSessions: '暂无历史会话',
          chatSession: 'AI 会话',
          untitled: '未命名会话',
          calendar: '财经日历',
          highImpact: '高影响',
          today: '今天',
          all: '全部',
          loading: '加载中...',
          noEvents: '暂无事件',
          focusSymbol: '数据源上下文',
          symbol: '标的',
          symbolPlaceholder: '可选：搜索并指定本次对话的数据源',
          noSymbol: '输入关键词搜索',
          estimatedCost: '本次约',
          scheduleCurrent: '定时分析',
          welcomeTitle: '用一句话开始控制 QuantDinger',
          welcomeDesc: '可以问行情、让它解释错误日志、写策略模板，或上传 K 线图一起判断。',
          placeholder: '例如：帮我诊断 BTC/USDT 1小时趋势，或者上传K线图问它是否适合开仓...',
          uploadChart: '上传K线图',
          send: '发送',
          watchlist: '我的自选',
          addWatchPlaceholder: '搜索并添加自选',
          addWatch: '添加自选',
          addWatchTitle: '添加自选标的',
          addWatchSearchPlaceholder: '输入股票、币种、外汇或期货代码',
          addWatchEmptyHint: '搜索标的，或从热门标的中选择',
          search: '搜索',
          selected: '已选择',
          add: '添加',
          noWatchlist: '暂无自选',
          ask: '问AI',
          schedule: '定时',
          remove: '删除',
          removeWatchConfirm: '确定从自选中删除这个标的吗？',
          monitors: 'AI定时分析任务',
          noMonitors: '暂无定时分析任务',
          running: '运行中',
          paused: '已暂停',
          eventDetail: '财经事件详情',
          actual: '实际',
          forecast: '预测',
          previous: '前值',
          aiPreview: 'AI影响预判',
          askAiEvent: '让AI深入分析',
          close: '关闭',
          createMonitor: '创建AI定时分析任务',
          interval: '分析频率',
          notify: '通知渠道',
          monitorTip: '系统会按频率分析当前标的，并在命中风险或机会时记录结果。',
          save: '保存',
          cancel: '取消',
          addWatchSuccess: '已加入自选',
          addWatchFailed: '添加自选失败',
          removeWatchSuccess: '已从自选删除',
          removeWatchFailed: '删除自选失败',
          deleteSessionConfirm: '确定删除这段会话历史吗？',
          sessionDeleted: '会话已删除',
          sessionDeleteFailed: '删除会话失败',
          monitorCreated: '定时任务已创建',
          monitorUpdated: '任务状态已更新',
          monitorDeleted: '任务已删除',
          strategyFlowTitle: '选择要创建的策略类型',
          indicatorStrategy: '策略研发',
          indicatorStrategyDesc: '基于已选标的生成可落地到策略 IDE 的研究、代码和回测方案',
          scriptStrategy: '脚本策略',
          scriptStrategyDesc: '生成 Python ScriptStrategy，适合复杂逻辑和自动执行',
          tradingBot: '模板策略',
          tradingBotDesc: '按标的行情推荐网格、趋势、DCA 或马丁模板策略参数',
          analysisRunning: '正在生成专业分析报告...',
          analysisComplete: '专业分析报告已生成',
          strategyGenerated: '策略草稿已生成',
          openTargetPage: '打开对应页面',
          chatUnavailable: 'Chat API 尚未接入，当前先以本地引导回复展示。',
          thinking: '思考中...',
          selectSymbolFirst: '请先在上方“数据源上下文”选择要诊断的标的。',
          uploadImage: '上传图片'
        }
      }
      return {
        title: 'AI Trading Copilot',
        subtitle: 'Search symbols, inspect events, analyze markets, diagnose strategies, and generate code from one workspace.',
        sessions: 'Chat History',
        newChat: 'New',
        noSessions: 'No history yet',
        chatSession: 'AI chat',
        untitled: 'Untitled chat',
        calendar: 'Economic Calendar',
        highImpact: 'High',
        today: 'Today',
        all: 'All',
        loading: 'Loading...',
        noEvents: 'No events',
        focusSymbol: 'Data context',
        symbol: 'Symbol',
        symbolPlaceholder: 'Optional: choose a data source for this chat',
        noSymbol: 'Type to search',
        estimatedCost: 'Est.',
        scheduleCurrent: 'Schedule',
        welcomeTitle: 'Control QuantDinger with plain language',
        welcomeDesc: 'Ask about markets, explain logs, draft strategies, or attach a chart screenshot.',
        placeholder: 'Example: diagnose BTC/USDT 1H trend, or upload a chart screenshot and ask whether entry risk is acceptable...',
        uploadChart: 'Upload chart',
        send: 'Send',
        watchlist: 'Watchlist',
        addWatchPlaceholder: 'Search and add to watchlist',
        addWatch: 'Add to watchlist',
        addWatchTitle: 'Add Watchlist Symbol',
        addWatchSearchPlaceholder: 'Enter a stock, crypto, forex, or futures symbol',
        addWatchEmptyHint: 'Search for a symbol, or choose from popular symbols',
        search: 'Search',
        selected: 'Selected',
        add: 'Add',
        noWatchlist: 'No watchlist',
        ask: 'Ask AI',
        schedule: 'Schedule',
        remove: 'Remove',
        removeWatchConfirm: 'Remove this symbol from watchlist?',
        deleteSessionConfirm: 'Delete this chat history?',
        sessionDeleted: 'Chat history deleted',
        sessionDeleteFailed: 'Failed to delete chat history',
        monitors: 'AI Scheduled Analysis',
        noMonitors: 'No scheduled tasks',
        running: 'Running',
        paused: 'Paused',
        eventDetail: 'Economic Event Detail',
        actual: 'Actual',
        forecast: 'Forecast',
        previous: 'Previous',
        aiPreview: 'AI Impact Preview',
        askAiEvent: 'Ask AI for detail',
        close: 'Close',
        createMonitor: 'Create AI scheduled analysis',
        interval: 'Interval',
        notify: 'Notification channels',
        monitorTip: 'The system will analyze this symbol on schedule and keep results for review.',
        save: 'Save',
        cancel: 'Cancel',
        addWatchSuccess: 'Added to watchlist',
        addWatchFailed: 'Failed to add watchlist item',
        removeWatchSuccess: 'Removed from watchlist',
        removeWatchFailed: 'Failed to remove watchlist item',
        monitorCreated: 'Scheduled task created',
        monitorUpdated: 'Task updated',
        monitorDeleted: 'Task deleted',
        strategyFlowTitle: 'Choose Strategy Workflow',
        indicatorStrategy: 'Strategy Lab',
        indicatorStrategyDesc: 'Develop a strategy workflow with research, code draft, and backtest plan',
        scriptStrategy: 'Script Strategy',
        scriptStrategyDesc: 'Generate a Python ScriptStrategy for complex automated logic',
        tradingBot: 'Template Strategy',
        tradingBotDesc: 'Recommend grid, trend, DCA, or martingale template strategy parameters from market context',
        analysisRunning: 'Generating professional analysis report...',
        analysisComplete: 'Professional analysis report generated',
        strategyGenerated: 'Strategy draft generated',
        openTargetPage: 'Open target page',
        chatUnavailable: 'Chat API is not implemented yet; showing a local guide response for now.',
        thinking: 'Thinking...',
        selectSymbolFirst: 'Choose a symbol in Data context before running diagnosis.',
        uploadImage: 'Upload image'
      }
    },
    uploadImageLabel () {
      return this.text.uploadImage || (this.isZh ? '上传图片' : 'Upload image')
    },
    thinkingText () {
      return this.text.thinking || (this.isZh ? '思考中...' : 'Thinking...')
    },
    quickPrompts () {
      const symbol = this.context.symbol || (this.isZh ? '当前标的' : 'this symbol')
      return [
        {
          key: 'diagnose',
          action: 'analysis',
          icon: 'line-chart',
          label: this.isZh ? '诊断标的' : 'Diagnose',
          prompt: this.isZh
            ? `请从趋势、量能、关键支撑阻力、资金面和风险角度分析 ${symbol}。`
            : `Analyze ${symbol} from trend, volume, key support/resistance, capital flow, and risk.`
        },
        {
          key: 'strategy',
          action: 'strategy',
          icon: 'code',
          label: this.isZh ? '写策略' : 'Write strategy',
          prompt: this.isZh
            ? `请为 ${symbol} 写一个稳健的策略模板，并说明参数、风控和适用市场。`
            : `Draft a robust strategy template for ${symbol}, including parameters, risk controls, and suitable market conditions.`
        },
        {
          key: 'logs',
          action: 'prompt',
          icon: 'bug',
          label: this.isZh ? '排查日志' : 'Debug logs',
          prompt: this.isZh
            ? '我会粘贴策略日志，请帮我定位异常原因并给出修复建议。'
            : 'I will paste strategy logs. Find the root cause and suggest fixes.'
        },
        {
          key: 'radar',
          action: 'prompt',
          icon: 'radar-chart',
          label: this.isZh ? '机会雷达' : 'Radar',
          prompt: this.isZh
            ? `请基于 ${symbol} 当前上下文，判断未来24小时是否有交易机会，并给出触发条件。`
            : `Based on ${symbol}, judge whether there is a trading opportunity in the next 24 hours and list trigger conditions.`
        }
      ]
    },
    systemQuickTasks () {
      const symbol = this.context.symbol || (this.isZh ? '当前标的' : 'this symbol')
      return [
        {
          key: 'diagnose',
          action: 'analysis',
          icon: 'line-chart',
          tone: 'analysis',
          label: this.isZh ? '诊断标的' : 'Diagnose',
          desc: this.isZh ? '趋势、量能、支撑阻力和风险' : 'Trend, volume, levels, and risk',
          prompt: this.isZh
            ? `请从趋势、量能、关键支撑阻力、资金面和风险角度分析 ${symbol}。`
            : `Analyze ${symbol} from trend, volume, key support/resistance, capital flow, and risk.`
        },
        {
          key: 'chart',
          action: 'prompt',
          icon: 'picture',
          tone: 'chart',
          label: this.isZh ? '看图诊断' : 'Chart review',
          desc: this.isZh ? '上传 K 线图，判断入场与止损' : 'Paste a chart for entry and stop review',
          prompt: this.isZh
            ? '我会上传一张 K 线图。请结合图形结构、趋势位置、量能、支撑阻力和风险收益比，判断当前是否适合入场，并给出止损、止盈和失效条件。'
            : 'I will paste or upload a chart. Review structure, trend location, volume, support/resistance, and risk/reward, then decide whether entry is appropriate with stop/take-profit/invalidation conditions.'
        },
        {
          key: 'strategy',
          action: 'strategy',
          icon: 'code',
          tone: 'strategy',
          label: this.isZh ? '写策略' : 'Write strategy',
          desc: this.isZh ? '指标 IDE、脚本策略、模板策略工作流' : 'Indicator, script, or template strategy workflow',
          prompt: this.isZh
            ? `请为 ${symbol} 设计一个稳健的策略模板，并说明参数、风控和适用市场。`
            : `Draft a robust strategy template for ${symbol}, including parameters, risk controls, and suitable market conditions.`
        },
        {
          key: 'monitor',
          action: 'prompt',
          icon: 'clock-circle',
          tone: 'monitor',
          label: this.isZh ? '定时跟踪' : 'Scheduled scan',
          desc: this.isZh ? '按周期自动复盘标的变化' : 'Track a symbol on a schedule',
          prompt: this.isZh
            ? `请帮我为 ${symbol} 规划一个 AI 定时分析任务。请先判断还缺哪些参数，并询问我周期、通知方式和重点关注条件；如果信息已足够，请整理成可创建任务的配置草案。`
            : `Help me plan a scheduled AI analysis task for ${symbol}. First identify missing fields and ask for interval, notification channel, and focus conditions; if enough information is present, draft a task configuration.`
        },
        {
          key: 'news',
          action: 'prompt',
          icon: 'global',
          tone: 'research',
          label: this.isZh ? '新闻研判' : 'News research',
          desc: this.isZh ? '检索新闻、事件和催化因素' : 'Search news, events, and catalysts',
          prompt: this.isZh
            ? '请围绕当前问题和标的检索最新新闻、公司事件和宏观催化因素，并说明对价格、风险和后续观察点的影响。'
            : 'Search recent news, company events, and macro catalysts for the current question and symbol, then explain price impact, risks, and follow-up signals.'
        },
        {
          key: 'logs',
          action: 'prompt',
          icon: 'bug',
          tone: 'debug',
          label: this.isZh ? '排查日志' : 'Debug logs',
          desc: this.isZh ? '定位策略、机器人或接口异常' : 'Find strategy, bot, or API failures',
          prompt: this.isZh
            ? '我会粘贴策略、模板策略或接口日志。请帮我定位异常原因，说明影响范围，并给出可执行的修复步骤。'
            : 'I will paste strategy, bot, or API logs. Find the root cause, explain impact, and suggest fixes.'
        },
        {
          key: 'macro',
          action: 'prompt',
          icon: 'fund',
          tone: 'macro',
          label: this.isZh ? '宏观数据' : 'Macro data',
          desc: this.isZh ? 'CPI、非农、利率和风险资产联动' : 'CPI, NFP, rates, and risk-asset links',
          prompt: this.isZh
            ? '请查询并整理相关宏观经济数据或事件，包括发布时间、实际值、预期值、前值、市场影响和可交易观察点。'
            : 'Look up relevant macroeconomic data or events, including release time, actual, forecast, previous, market impact, and tradable watch points.'
        },
        {
          key: 'radar',
          action: 'prompt',
          icon: 'radar-chart',
          tone: 'radar',
          label: this.isZh ? '机会雷达' : 'Radar',
          desc: this.isZh ? '筛选未来 24 小时触发条件' : 'Find 24h opportunity triggers',
          prompt: this.isZh
            ? `请基于 ${symbol} 当前上下文，判断未来 24 小时是否有交易机会，并给出触发条件、失效条件和需要重点观察的数据。`
            : `Based on ${symbol}, judge whether there is a trading opportunity in the next 24 hours and list trigger conditions.`
        }
      ]
    },
    quickTaskDisplayText () {
      if (this.isZh) {
        return {
          market_diagnosis: {
            label: '诊断标的',
            desc: '趋势、量能、支撑阻力、资金面和风险'
          },
          chart_review: {
            label: '看图诊断',
            desc: '上传图表，判断入场、止损和失效条件'
          },
          indicator_strategy: {
            label: '策略研发',
            desc: '生成可在策略 IDE 展示、回测和发布的策略草稿'
          },
          scheduled_analysis: {
            label: '定时跟踪',
            desc: '按周期自动复盘标的变化并保存结果'
          },
          news_research: {
            label: '新闻/事件检索',
            desc: '联网检索公司、资产、宏观事件和行业新闻'
          },
          debug_logs: {
            label: '排查日志',
            desc: '定位策略、机器人、接口异常'
          },
          macro_economic_data: {
            label: '宏观经济数据',
            desc: '查询非农、CPI、FOMC、利率、GDP、PCE 等全球宏观事件和市场影响'
          },
          opportunity_radar: {
            label: '机会雷达',
            desc: '筛选未来 24 小时可能触发的机会条件'
          }
        }
      }
      return {
        market_diagnosis: {
          label: 'Diagnose symbol',
          desc: 'Trend, volume, key levels, flows, and risks'
        },
        chart_review: {
          label: 'Chart review',
          desc: 'Upload a chart for entry, stop, and invalidation review'
        },
        indicator_strategy: {
          label: 'Strategy Lab',
          desc: 'Draft a Strategy IDE workflow for chart display, backtesting, and publishing'
        },
        scheduled_analysis: {
          label: 'Scheduled scan',
          desc: 'Track symbol changes on schedule and keep results'
        },
        news_research: {
          label: 'News/Event research',
          desc: 'Search company, asset, macro, and industry events'
        },
        debug_logs: {
          label: 'Debug logs',
          desc: 'Find strategy, bot, or API failures'
        },
        macro_economic_data: {
          label: 'Macro data',
          desc: 'Inspect NFP, CPI, FOMC, rates, GDP, PCE, and market impact'
        },
        opportunity_radar: {
          label: 'Opportunity radar',
          desc: 'Find possible 24h opportunity triggers'
        }
      }
    },
    registeredQuickTasks () {
      const registry = Array.isArray(this.skillRegistry) ? this.skillRegistry : []
      if (!registry.length) return this.systemQuickTasks

      const order = [
        'market_diagnosis',
        'chart_review',
        'indicator_strategy',
        'scheduled_analysis',
        'news_research',
        'debug_logs',
        'macro_economic_data',
        'opportunity_radar'
      ]
      const byId = new Map(registry.map(item => [item.id, item]))
      return order
        .map(id => byId.get(id))
        .filter(Boolean)
        .map(skill => {
          const actionType = skill.action_type || ''
          const displayText = this.quickTaskDisplayText[skill.id] || {}
          return {
            key: skill.id,
            skillId: skill.id,
            action: actionType === 'strategy'
              ? 'strategy'
              : actionType === 'addWatch'
                ? 'addWatch'
                : skill.id === 'market_diagnosis'
                  ? 'analysis'
                  : skill.id === 'scheduled_analysis'
                    ? 'monitor'
                    : 'prompt',
            icon: skill.icon || 'appstore',
            tone: (skill.ui && skill.ui.tone) || skill.category || '',
            label: displayText.label || skill.label,
            desc: displayText.desc || skill.description,
            prompt: skill.prompt || ''
          }
        })
    },
    strategyTargets () {
      return [
        {
          key: 'indicator',
          icon: 'line-chart',
          title: this.text.indicatorStrategy,
          desc: this.text.indicatorStrategyDesc
        },
        {
          key: 'script',
          icon: 'code',
          title: this.text.scriptStrategy,
          desc: this.text.scriptStrategyDesc
        },
        {
          key: 'bot',
          icon: 'robot',
          title: this.text.tradingBot,
          desc: this.text.tradingBotDesc
        }
      ]
    },
    estimatedCost () {
      if (this.billing && this.billing.billing_enabled === false) {
        return this.isZh ? '免费' : 'Free'
      }
      const costs = this.billing.feature_costs || {}
      const chat = Number(costs.ai_copilot_chat || 0)
      const img = this.attachments.length > 0 ? Number(costs.ai_copilot_image || 0) : 0
      return `${chat + img} credits`
    },
    canSend () {
      return !this.sending && (this.draft.trim().length > 0 || this.attachments.length > 0)
    },
    currentContextLabel () {
      const target = this.normalizeSymbolOption(this.context)
      if (!target || !target.symbol) return this.isZh ? '未指定，AI 将按问题自动识别' : 'Not fixed; AI will infer from your message'
      return `${target.market}:${target.symbol}`
    },
    selectableSymbols () {
      const map = new Map()
      ;(this.watchlist || []).forEach(item => {
        const normalized = this.normalizeSymbolOption(item)
        if (normalized) map.set(this.symbolOptionValue(normalized), normalized)
      })
      ;(this.symbolOptions || []).forEach(item => {
        const normalized = this.normalizeSymbolOption(item)
        if (normalized) map.set(this.symbolOptionValue(normalized), normalized)
      })
      const current = this.normalizeSymbolOption(this.context)
      if (current) map.set(this.symbolOptionValue(current), current)
      return Array.from(map.values())
    },
    displayCalendarEvents () {
      const list = Array.isArray(this.calendarEvents) ? this.calendarEvents : []
      const today = new Date().toISOString().slice(0, 10)
      if (this.calendarFilter === 'today') {
        return list.filter(e => String(e.date || e.datetime || '').slice(0, 10) === today).slice(0, 12)
      }
      if (this.calendarFilter === 'high') {
        return list.filter(e => this.impactClass(e) === 'high').slice(0, 12)
      }
      return list.slice(0, 16)
    },
    taskSymbolLabel () {
      const target = this.taskTarget || this.normalizeSymbolOption(this.context)
      if (!target) return '--'
      return `${this.marketLabel(target.market)} · ${target.symbol}`
    }
  },
  mounted () {
    this.loadMarketModules()
    this.seedSymbolOptions()
    this.loadBilling()
    this.loadWatchlist()
    this.loadSessions()
    this.loadMonitors()
    this.loadAgentPreflight()
    this.loadAiSkills()
    this.loadUserMemories()
    this.$nextTick(this.resizeComposer)
  },
  beforeDestroy () {
    if (this.symbolSearchTimer) clearTimeout(this.symbolSearchTimer)
    if (this.addWatchSearchTimer) clearTimeout(this.addWatchSearchTimer)
  },
  methods: {
    resizeComposer () {
      const el = this.$refs && this.$refs.composerInput
      if (!el) return
      el.style.height = 'auto'
      const next = Math.max(this.composerMinHeight, Math.min(this.composerMaxHeight, el.scrollHeight || this.composerMinHeight))
      this.composerHeight = next
      el.style.height = `${next}px`
      el.style.overflowY = (el.scrollHeight || 0) > this.composerMaxHeight ? 'auto' : 'hidden'
    },
    selectedContextTarget () {
      return this.normalizeSymbolOption(this.context)
    },
    quickTaskRequiresSymbol (item) {
      const key = String((item && (item.key || item.skillId || item.id)) || '').toLowerCase()
      const requiredKeys = new Set([
        'diagnose',
        'market_diagnosis',
        'indicator_strategy',
        'scheduled_analysis',
        'monitor',
        'opportunity_radar',
        'radar'
      ])
      return !!item && (item.action === 'analysis' || requiredKeys.has(key))
    },
    promptSelectSymbolFirst () {
      this.$message.warning(this.text.selectSymbolFirst || (this.isZh ? '请先选择要诊断的标的。' : 'Choose a symbol first.'))
      this.seedSymbolOptions()
      this.$nextTick(() => {
        const picker = this.$refs && this.$refs.contextSymbolSelect
        if (picker && typeof picker.focus === 'function') picker.focus()
      })
    },
    selectedTargetLabel (target) {
      const item = this.normalizeSymbolOption(target)
      if (!item) return ''
      return `${item.market}:${item.symbol}${item.name ? ` (${item.name})` : ''}`
    },
    buildLockedQuickPrompt (item, target) {
      const key = String((item && (item.key || item.skillId || item.id)) || '').toLowerCase()
      const label = this.selectedTargetLabel(target)
      if (key === 'indicator_strategy') {
        return this.isZh
          ? [
              `请基于已选数据上下文 ${label} 做一次 QuantDinger 策略研发。`,
              '',
              '要求：',
              '1. 本次任务必须锁定到已选标的，不要因为提示词或示例里出现其他标的而切换上下文。',
              '2. 生成可落地到策略 IDE 的 Python 策略草稿，当前优先使用指标策略工作流。',
              '3. 若输出指标策略代码，必须使用 QuantDinger 执行约定：df 四方向布尔列 open_long、close_long、open_short、close_short 是回测和实盘信号来源。',
              '4. 说明核心参数、买卖信号、止损止盈、失效条件和适用行情。',
              '5. 代码注释使用英文，解释文字可以使用当前界面语言。'
            ].join('\n')
          : [
              `Run QuantDinger strategy research for the selected data context ${label}.`,
              '',
              'Requirements:',
              '1. Lock this task to the selected symbol; do not switch context because another symbol appears in examples.',
              '2. Generate a Python strategy draft that can land in Strategy IDE; prefer the indicator-strategy workflow for now.',
              '3. If you output indicator-strategy code, use the QuantDinger contract: df boolean columns open_long, close_long, open_short, and close_short are the backtest/live signals.',
              '4. Explain parameters, entry/exit signals, stop/take-profit logic, invalidation, and suitable market regimes.',
              '5. Keep code comments in English.'
            ].join('\n')
      }
      if (key === 'opportunity_radar' || key === 'radar') {
        return this.isZh
          ? [
              `请基于已选数据上下文 ${label} 做一次机会雷达扫描。`,
              '',
              '要求：',
              '1. 不要切换到其他示例标的，不要因为提示词中的示例词改变分析对象。',
              '2. 结合系统行情、新闻/事件、宏观环境、关键价位、量能和风险收益比。',
              '3. 判断未来 24 小时是否存在可执行机会，并区分做多、做空、观望三种场景。',
              '4. 给出触发条件、失效条件、止损思路、观察指标和优先级。',
              '5. 如果系统数据缺失，明确说明缺口，并给出用户可以补充的数据。'
            ].join('\n')
          : [
              `Run an opportunity radar scan for the selected data context ${label}.`,
              '',
              'Requirements:',
              '1. Do not switch to another example symbol because of words inside the prompt.',
              '2. Use system market data, news/events, macro context, key levels, volume, and risk/reward.',
              '3. Judge whether the next 24 hours offer long, short, or wait scenarios.',
              '4. Provide triggers, invalidation, stop logic, watch metrics, and priority.',
              '5. If data is missing, state the gap and what the user should provide.'
            ].join('\n')
      }
      return item && item.prompt ? item.prompt : ''
    },
    beginMonitorSetup (target) {
      const normalized = this.normalizeSymbolOption(target)
      if (!normalized || !normalized.symbol) {
        this.promptSelectSymbolFirst()
        return
      }
      this.pendingAgentTask = {
        type: 'monitor_setup',
        target: normalized,
        required: ['interval_min', 'notify_channels', 'focus_conditions']
      }
      this.messages.push({
        localId: `local-${localId++}`,
        role: 'assistant',
        content: this.buildMonitorQuestion(normalized),
        meta: this.isZh ? '等待任务参数' : 'waiting for task parameters',
        created_at: new Date().toISOString()
      })
      this.scrollToBottom()
    },
    clearThinkingMessage (assistantMsg) {
      if (!assistantMsg || !assistantMsg.isThinking) return
      assistantMsg.content = ''
      assistantMsg.isThinking = false
    },
    replacePendingAssistant (assistantMsg, nextMsg) {
      const idx = this.messages.indexOf(assistantMsg)
      if (idx >= 0) this.messages.splice(idx, 1, nextMsg)
      else this.messages.push(nextMsg)
      return nextMsg
    },
    async loadMarketModules () {
      const options = await loadEnabledMarketOptions({ includeFeatures: ['research'] })
      this.markets = options.map(item => ({
        value: item.value,
        label: item.label || item.value,
        i18nKey: item.i18nKey,
        module: item.module
      }))
      const values = this.markets.map(item => item.value)
      if (!values.includes(this.addWatchMarket)) {
        this.addWatchMarket = firstMarketValue(this.markets)
      }
      if (this.context.market && !values.includes(this.context.market)) {
        this.context = { market: '', symbol: '' }
      }
    },
    async loadAiSkills () {
      this.loadingSkills = true
      try {
        const res = await getAiSkills({ language: this.isZh ? 'zh-CN' : 'en-US' })
        const data = res.data || {}
        this.skillRegistry = Array.isArray(data.skills) ? data.skills : []
      } catch (_) {
        this.skillRegistry = []
      } finally {
        this.loadingSkills = false
      }
    },
    async loadBilling () {
      try {
        const res = await getMembershipPlans()
        const data = res.data || {}
        this.billing = data.billing || data.billing_config || {}
      } catch (_) {}
    },
    async loadCalendar (force = false) {
      this.loadingCalendar = true
      this.calendarError = ''
      try {
        const res = await getEconomicCalendar({ force: force ? 1 : 0, days: 14, lang: this.isZh ? 'zh-CN' : 'en-US' })
        const data = res.data || {}
        this.calendarEvents = Array.isArray(data) ? data : (data.events || data.calendar || [])
      } catch (e) {
        this.calendarError = (e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || (this.isZh ? '财经日历暂不可用' : 'Calendar unavailable')
      } finally {
        this.loadingCalendar = false
      }
    },
    async loadWatchlist () {
      try {
        const res = await getWatchlist()
        const list = Array.isArray(res.data) ? res.data : ((res.data && res.data.watchlist) || [])
        this.watchlist = list.map(x => this.normalizeSymbolOption(x)).filter(Boolean)
        this.seedSymbolOptions()
        if (this.watchlist.length) {
          const prices = await getWatchlistPrices({ watchlist: this.watchlist.slice(0, 24).map(x => ({ market: x.market, symbol: x.symbol })) })
          this.watchlistPrices = this.normalizePriceMap(prices.data || {})
        }
      } catch (_) {
        this.watchlist = []
      }
    },
    async loadMonitors () {
      this.loadingMonitors = true
      try {
        const res = await getMonitors()
        this.monitors = res && res.code === 1 ? (res.data || []) : []
      } catch (_) {
        this.monitors = []
      } finally {
        this.loadingMonitors = false
      }
    },
    async loadSessions () {
      try {
        const res = await getChatSessions()
        this.sessions = Array.isArray(res.data) ? res.data : ((res.data && res.data.sessions) || [])
      } catch (_) {}
    },
    async loadHistory (sessionId) {
      this.sessionId = sessionId
      try {
        const res = await getChatHistory({ session_id: sessionId })
        const rawMessages = Array.isArray(res.data) ? res.data : ((res.data && res.data.messages) || [])
        this.messages = this.normalizeMessages(rawMessages)
        this.scrollToBottom()
      } catch (_) {}
    },
    messagePersistContent (message) {
      if (!message) return ''
      const content = String(message.content || '').trim()
      if (content) return content
      if (message.report) {
        const report = message.report || {}
        const target = message.reportTarget || {}
        const market = report.market || target.market || ''
        const symbol = report.symbol || target.symbol || ''
        return `Analysis report: ${[market, symbol].filter(Boolean).join(':') || 'market'}`
      }
      if (message.reportError) return `Analysis failed: ${message.reportError}`
      return String(message.meta || '').trim()
    },
    async persistCopilotMessage (message, intent = '') {
      if (!message) return null
      const content = this.messagePersistContent(message)
      if (!content && !message.report && !message.reportError) return null
      try {
        const context = this.buildChatContext ? this.buildChatContext(message.content) : {}
        const res = await saveCopilotMessage({
          session_id: this.sessionId,
          message_id: message.id || null,
          role: message.role || 'assistant',
          content,
          attachments: message.attachments || [],
          actions: message.actions || [],
          report: message.report || null,
          reportTarget: message.reportTarget || null,
          reportError: message.reportError || '',
          reportErrorTone: message.reportErrorTone || '',
          intent: intent || message.meta || 'local_agent',
          context
        })
        const data = res && res.data ? res.data : {}
        if (data.session_id) this.sessionId = data.session_id
        if (data.message_id) this.$set ? this.$set(message, 'id', data.message_id) : (message.id = data.message_id)
        await this.loadSessions()
        return data
      } catch (_) {
        return null
      }
    },
    async removeSession (session) {
      if (!session || !session.id) return
      try {
        const res = await deleteChatSession(session.id)
        if (!res || res.code === 0) throw new Error((res && res.msg) || this.text.sessionDeleteFailed)
        this.$message.success(this.text.sessionDeleted)
        if (this.sessionId === session.id) {
          this.sessionId = null
          this.messages = []
        }
        await this.loadSessions()
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || this.text.sessionDeleteFailed)
      }
    },
    newSession () {
      this.sessionId = null
      this.messages = []
    },
    seedSymbolOptions () {
      this.symbolOptions = (this.watchlist || []).filter(item => !this.context.market || item.market === this.context.market)
      if (!this.symbolOptions.length && this.context.symbol) {
        this.symbolOptions = [{ market: this.context.market, symbol: this.context.symbol }]
      }
    },
    handleSymbolSearch (keyword) {
      if (this.symbolSearchTimer) clearTimeout(this.symbolSearchTimer)
      this.symbolSearchTimer = setTimeout(() => this.doSymbolSearch(keyword), 260)
    },
    async doSymbolSearch (keyword) {
      const kw = String(keyword || '').trim()
      if (!kw) {
        this.seedSymbolOptions()
        return
      }
      this.symbolSearching = true
      try {
        const params = { keyword: kw, limit: 14 }
        if (this.context.market) params.market = this.context.market
        const res = await searchSymbols(params)
        const data = res.data || {}
        const list = Array.isArray(data) ? data : (data.results || data.symbols || data.items || [])
        this.symbolOptions = list.map(x => this.normalizeSymbolOption(x)).filter(Boolean)
      } catch (_) {
        const inferred = this.inferSymbolFromText(kw)
        this.symbolOptions = [{ market: (inferred && inferred.market) || this.context.market || firstMarketValue(this.markets), symbol: kw.toUpperCase() }]
      } finally {
        this.symbolSearching = false
      }
    },
    handleSymbolChange (value) {
      if (!value) {
        this.context.market = ''
        this.context.symbol = ''
        return
      }
      const item = this.selectableSymbols.find(x => this.symbolOptionValue(x) === value) || this.parseSymbolValue(value)
      this.context.market = item.market || this.context.market
      this.context.symbol = item.symbol || ''
      this.selectedSymbolValue = this.symbolOptionValue(item)
      this.seedSymbolOptions()
    },
    addWatchSymbol () {
      this.openAddWatchModal()
    },
    async openAddWatchModal () {
      this.addWatchModalVisible = true
      this.addWatchMarket = this.context.market || this.addWatchMarket || 'Crypto'
      this.addWatchKeyword = ''
      this.addWatchSelected = null
      await this.loadAddWatchHotSymbols()
    },
    closeAddWatchModal () {
      this.addWatchModalVisible = false
      this.addWatchKeyword = ''
      this.addWatchResults = []
      this.addWatchSelected = null
      this.addWatchSearching = false
      if (this.addWatchSearchTimer) {
        clearTimeout(this.addWatchSearchTimer)
        this.addWatchSearchTimer = null
      }
    },
    handleAddWatchMarketChange (market) {
      this.addWatchMarket = market
      this.addWatchKeyword = ''
      this.addWatchSelected = null
      this.loadAddWatchHotSymbols()
    },
    handleAddWatchKeywordChange () {
      if (this.addWatchSearchTimer) clearTimeout(this.addWatchSearchTimer)
      this.addWatchSearchTimer = setTimeout(() => {
        this.searchAddWatchSymbols(this.addWatchKeyword)
      }, 260)
    },
    async loadAddWatchHotSymbols () {
      this.addWatchSearching = true
      try {
        const res = await getHotSymbols({ market: this.addWatchMarket, limit: 10 })
        const data = res.data || {}
        const list = Array.isArray(data) ? data : (data.results || data.symbols || data.items || [])
        this.addWatchResults = list.map(x => this.normalizeSymbolOption({ ...x, market: x.market || this.addWatchMarket })).filter(Boolean)
      } catch (_) {
        this.addWatchResults = []
      } finally {
        this.addWatchSearching = false
      }
    },
    async searchAddWatchSymbols (keyword) {
      const kw = String(keyword || '').trim()
      if (!kw) {
        await this.loadAddWatchHotSymbols()
        return
      }
      this.addWatchSearching = true
      this.addWatchSelected = null
      try {
        const res = await searchSymbols({ market: this.addWatchMarket, keyword: kw, limit: 16 })
        const data = res.data || {}
        const list = Array.isArray(data) ? data : (data.results || data.symbols || data.items || [])
        const normalized = list.map(x => this.normalizeSymbolOption({ ...x, market: x.market || this.addWatchMarket })).filter(Boolean)
        this.addWatchResults = normalized.length ? normalized : [{ market: this.addWatchMarket, symbol: kw.toUpperCase(), name: '' }]
      } catch (_) {
        this.addWatchResults = [{ market: this.addWatchMarket, symbol: kw.toUpperCase(), name: '' }]
      } finally {
        this.addWatchSearching = false
      }
    },
    selectAddWatchSymbol (item) {
      this.addWatchSelected = this.normalizeSymbolOption(item)
    },
    async confirmAddWatchSymbol () {
      const item = this.normalizeSymbolOption(this.addWatchSelected)
      if (!item || !item.symbol) {
        this.$message.warning(this.text.addWatchEmptyHint)
        return
      }
      this.addingWatch = true
      try {
        const res = await addWatchlist({ market: item.market, symbol: item.symbol, name: item.name || item.symbol })
        if (!res || res.code === 0) throw new Error((res && res.msg) || this.text.addWatchFailed)
        this.$message.success(this.text.addWatchSuccess)
        this.closeAddWatchModal()
        await this.loadWatchlist()
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || this.text.addWatchFailed)
      } finally {
        this.addingWatch = false
      }
    },
    async removeWatch (item) {
      const normalized = this.normalizeSymbolOption(item)
      if (!normalized || !normalized.symbol) return
      try {
        const res = await removeWatchlist({ market: normalized.market, symbol: normalized.symbol })
        if (!res || res.code === 0) throw new Error((res && res.msg) || this.text.removeWatchFailed)
        this.$message.success(this.text.removeWatchSuccess)
        if (this.selectedSymbolValue === this.symbolOptionValue(normalized)) {
          this.selectedSymbolValue = ''
        }
        await this.loadWatchlist()
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || this.text.removeWatchFailed)
      }
    },
    selectWatch (item) {
      const normalized = this.normalizeSymbolOption(item)
      this.context.market = normalized.market
      this.context.symbol = normalized.symbol
      this.selectedSymbolValue = this.symbolOptionValue(normalized)
      this.seedSymbolOptions()
    },
    askWatch (item) {
      this.selectWatch(item)
      this.usePrompt(this.isZh
        ? `请分析 ${item.symbol} 当前走势，重点关注趋势、量能、支撑阻力、风险和是否值得入场。`
        : `Analyze ${item.symbol}: trend, volume, support/resistance, risk, and whether entry is reasonable.`)
    },
    openEventDetail (event) {
      this.selectedEvent = event
      this.eventModalVisible = true
    },
    askAboutEvent (event, sendNow = false) {
      const title = this.eventTitle(event)
      this.draft = this.isZh
        ? `请深入分析财经事件「${title}」可能对 ${this.context.symbol || '当前标的'} 的影响，重点说明方向偏向、波动窗口、风险点和交易上应避免的动作。`
        : `Analyze how the economic event "${title}" may affect ${this.context.symbol || 'the selected symbol'}, including directional bias, volatility window, risk points, and trading actions to avoid.`
      this.eventModalVisible = false
      if (sendNow) this.$nextTick(() => this.sendMessage())
    },
    eventPreview (event) {
      const impact = this.impactClass(event)
      const symbol = this.context.symbol || (this.isZh ? '当前标的' : 'the selected symbol')
      if (this.isZh) {
        if (impact === 'high') return `该事件属于高影响事件，发布前后可能显著放大 ${symbol} 的滑点和波动。建议重点观察公布前30分钟到公布后60分钟，避免无保护追单。`
        if (impact === 'low') return `该事件影响通常有限，但若与当前市场叙事一致，仍可能成为短线波动的辅助因素。`
        return `该事件可能带来中等波动，建议结合实际值、预测值和市场当前趋势判断，不宜只按事件名称做方向判断。`
      }
      if (impact === 'high') return `This is a high-impact event. Slippage and volatility may expand around ${symbol}. Watch the window from 30 minutes before to 60 minutes after release.`
      if (impact === 'low') return 'This event is usually low impact, but it may still support short-term moves if it matches the current market narrative.'
      return 'This event may create moderate volatility. Compare actual, forecast, and prevailing trend before forming a directional view.'
    },
    usePrompt (prompt, options = {}) {
      this.draft = prompt
      const lockTarget = options && options.contextLock ? this.normalizeSymbolOption(options.contextLock) : null
      this.draftContextLock = lockTarget ? { ...lockTarget, locked: true } : null
      this.$nextTick(() => {
        this.resizeComposer()
        if (this.$refs.composerInput) this.$refs.composerInput.focus()
      })
    },
    async loadAgentPreflight () {
      try {
        const res = await getAgentPreflight()
        this.agentPreflight = res.data || res
      } catch (_) {
        this.agentPreflight = null
      }
    },
    async loadUserMemories () {
      try {
        const res = await getUserMemory()
        const data = res.data || res
        this.userMemories = (data && data.items) || []
      } catch (_) {
        this.userMemories = []
      }
    },
    buildPreflightGuide (task = null) {
      const status = this.agentPreflight || {}
      const blockers = Array.isArray(status.blockers) ? status.blockers : []
      const warnings = Array.isArray(status.warnings) ? status.warnings : []
      if (!blockers.length && !warnings.length) return null
      const lines = []
      const actions = []
      lines.push(`## ${this.i18nText('aiCopilot.preflight.title', this.isZh ? '开始前检查' : 'Setup Check')}`, '')
      if (blockers.length) {
        lines.push(this.i18nText('aiCopilot.preflight.blockersIntro', this.isZh ? '这些问题会影响 AI 工作流：' : 'These items need attention before the AI workflow can run:'))
      }
      blockers.forEach(item => {
        const isCredits = this.isCreditPreflightItem(item)
        const title = isCredits
          ? this.i18nText('aiCopilot.preflight.creditsTitle', this.isZh ? '积分不足' : 'Insufficient credits')
          : (item.title || item.key)
        const message = isCredits
          ? this.i18nText('aiCopilot.preflight.creditsMessage', this.isZh ? '你的积分余额不足，暂时无法运行 AI 分析或策略生成。充值后即可继续使用。' : 'You do not have enough credits to run AI analysis or strategy generation. Top up credits to continue.')
          : (item.message || '')
        lines.push(`- **${title}**: ${message}`)
        if (isCredits) {
          this.pushPreflightAction(actions, this.setupAction('billing'))
          this.pushPreflightAction(actions, this.setupAction('credits'))
        } else if (item.action && item.action.path) {
          this.pushPreflightAction(actions, {
            key: `fix-${item.key}`,
            icon: item.action.icon || 'setting',
            label: this.i18nText('aiCopilot.preflight.configureAction', this.isZh ? '去配置' : 'Configure'),
            path: item.action.path,
            query: item.action.query || {}
          })
        }
      })
      if (warnings.length) {
        lines.push('', this.i18nText('aiCopilot.preflight.recommendedNext', this.isZh ? '建议补齐：' : 'Recommended next:'))
        warnings.slice(0, 4).forEach(item => {
          const isCredits = this.isCreditPreflightItem(item)
          lines.push(`- ${isCredits ? this.i18nText('aiCopilot.preflight.creditsMessage', this.isZh ? '你的积分余额不足，暂时无法运行 AI 分析或策略生成。充值后即可继续使用。' : 'You do not have enough credits to run AI analysis or strategy generation. Top up credits to continue.') : (item.message || item.key)}`)
          if (isCredits) {
            this.pushPreflightAction(actions, this.setupAction('billing'))
            this.pushPreflightAction(actions, this.setupAction('credits'))
          } else if (item.action && item.action.path) {
            this.pushPreflightAction(actions, {
              key: `open-${item.key}`,
              icon: item.action.icon || 'arrow-right',
              label: this.i18nText('aiCopilot.preflight.openAction', this.isZh ? '查看' : 'Open'),
              path: item.action.path,
              query: item.action.query || {}
            })
          }
        })
      }
      if (task) {
        lines.push('', this.i18nText('aiCopilot.preflight.taskContinue', this.isZh ? '你仍然可以继续讨论策略思路，但生成代码、运行分析或创建任务前建议先处理上面的项目。' : 'You can still discuss strategy ideas, but complete the items above before code generation, analysis, or task creation.'))
      }
      return {
        content: lines.join('\n'),
        actions,
        meta: this.i18nText('aiCopilot.preflight.meta', this.isZh ? '配置预检' : 'setup preflight')
      }
    },
    isCreditPreflightItem (item) {
      const actionPath = item && item.action && item.action.path ? item.action.path : ''
      const text = [
        item && item.key,
        item && item.title,
        item && item.message,
        actionPath
      ].filter(Boolean).join(' ').toLowerCase()
      return /credit|credits|billing|quota|payment|top\s*up|vip|积分|余额不足|额度|充值|会员|扣费/.test(text)
    },
    pushPreflightAction (actions, action) {
      if (!action) return
      const exists = actions.some(item => item.key === action.key || (item.path === action.path && JSON.stringify(item.query || {}) === JSON.stringify(action.query || {})))
      if (!exists) actions.push(action)
    },
    appendMemoryActions (assistantMsg, candidates) {
      const list = Array.isArray(candidates) ? candidates : []
      if (!list.length) return
      assistantMsg.actions = assistantMsg.actions || []
      list.slice(0, 2).forEach((candidate, index) => {
        assistantMsg.actions.push({
          key: `save-memory-${Date.now()}-${index}`,
          type: 'save_memory',
          icon: 'pushpin',
          label: this.isZh ? '记住这个偏好' : 'Remember this',
          payload: candidate
        })
      })
    },
    appendAgentNextActions (assistantMsg) {
      const task = this.pendingAgentTask
      if (!task || task.type !== 'strategy_design') return
      const labels = {
        indicator: this.isZh ? '生成指标 IDE 代码' : 'Generate Indicator IDE code',
        script: this.isZh ? '生成脚本策略代码' : 'Generate script strategy',
        bot: this.isZh ? '生成模板策略方案' : 'Generate template strategy plan'
      }
      assistantMsg.actions = assistantMsg.actions || []
      assistantMsg.actions.push({
        key: `generate-strategy-${Date.now()}`,
        type: 'generate_strategy_code',
        icon: task.targetType === 'bot' ? 'robot' : 'code',
        label: labels[task.targetType] || labels.indicator,
        payload: {
          task,
          prompt: task.originalPrompt || this.draft
        }
      })
    },
    isAllowedMessageActionPath (path) {
      const allowed = [
        '/settings',
        '/broker-accounts',
        '/billing',
        '/profile',
        '/indicator-ide',
        '/strategy-live',
        '/strategy-script',
        '/trading-bot',
        '/user/login'
      ]
      return allowed.includes(String(path || ''))
    },
    isAllowedMessageStorageKey (key) {
      const allowedPrefixes = [
        'qd_copilot_'
      ]
      return allowedPrefixes.some(prefix => String(key || '').startsWith(prefix))
    },
    runMessageAction (action) {
      if (action && action.type === 'save_memory') {
        this.saveMemoryAction(action.payload || {})
        return
      }
      if (action && action.type === 'generate_strategy_code') {
        this.generateStrategyFromAction(action.payload || {})
        return
      }
      if (action && action.type === 'create_monitor_task') {
        this.createMonitorFromAction(action.payload || {})
        return
      }
      if (action && action.type === 'export_report_pdf') {
        this.exportReportPdf(action.payload && action.payload.reportId)
        return
      }
      if (action && action.type === 'ask_about_report') {
        this.askAboutReport(action.payload && action.payload.reportId)
        return
      }
      if (!action || !action.path) return
      if (!this.isAllowedMessageActionPath(action.path)) {
        this.$message.warning(this.isZh ? '该操作不在允许的跳转范围内' : 'This action is not allowed')
        return
      }
      try {
        if (action.storageKey && this.isAllowedMessageStorageKey(action.storageKey)) {
          const value = typeof action.storageValue === 'string' ? action.storageValue : JSON.stringify(action.storageValue || {})
          sessionStorage.setItem(action.storageKey, value)
        }
        Object.keys(action.extraStorage || {}).forEach(key => {
          if (this.isAllowedMessageStorageKey(key)) {
            if (key === 'qd_copilot_indicator_prompt') return
            sessionStorage.setItem(key, action.extraStorage[key])
          }
        })
      } catch (_) {}
      this.$router.push({ path: action.path, query: action.query || {} })
    },
    workflowActionForMessage (msg) {
      const actions = Array.isArray(msg && msg.actions) ? msg.actions : []
      return actions.find(action => {
        const path = String(action && action.path ? action.path : '')
        return action && (
          action.group === 'strategy_workflow' ||
          path === '/indicator-ide' ||
          path === '/strategy-script' ||
          path === '/trading-bot'
        )
      }) || null
    },
    visibleMessageActions (msg) {
      const actions = Array.isArray(msg && msg.actions) ? msg.actions : []
      return actions.filter(action => action && action.type !== 'generate_strategy_code')
    },
    strategyCodeForMessage (msg) {
      const action = this.workflowActionForMessage(msg)
      if (action && typeof action.storageValue === 'string' && action.storageValue.trim()) return action.storageValue
      if (action && action.storageValue && typeof action.storageValue === 'object') return JSON.stringify(action.storageValue, null, 2)
      return this.extractFirstCodeBlock(msg && msg.content)
    },
    extractFirstCodeBlock (content) {
      const match = String(content || '').match(/```(?:\w+)?\s*([\s\S]*?)```/)
      return match ? match[1].trim() : ''
    },
    async copyStrategyCode (msg) {
      const code = this.strategyCodeForMessage(msg)
      if (!code) return
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(code)
        } else {
          const textarea = document.createElement('textarea')
          textarea.value = code
          textarea.style.position = 'fixed'
          textarea.style.opacity = '0'
          document.body.appendChild(textarea)
          textarea.select()
          document.execCommand('copy')
          document.body.removeChild(textarea)
        }
        this.$message.success(this.isZh ? '代码已复制' : 'Code copied')
      } catch (_) {
        this.$message.error(this.isZh ? '复制失败' : 'Copy failed')
      }
    },
    async saveMemoryAction (payload) {
      if (!payload || !payload.content) return
      try {
        await saveUserMemory({
          category: payload.category || 'preference',
          title: payload.title || (this.isZh ? '交易偏好' : 'Trading preference'),
          content: payload.content,
          confidence: payload.confidence || 70
        })
        this.$message.success(this.isZh ? '已加入个人记忆' : 'Saved to memory')
        this.loadUserMemories()
      } catch (e) {
        this.$message.error(this.isZh ? '保存记忆失败' : 'Failed to save memory')
      }
    },
    async generateStrategyFromAction (payload) {
      const task = payload.task || this.pendingAgentTask
      const target = this.normalizeSymbolOption((task && task.target) || this.context)
      const prompt = payload.prompt || this.draft || (task && task.originalPrompt) || ''
      if (!task || !target || !target.symbol) {
        this.$message.warning(this.text.symbolPlaceholder)
        return
      }
      if (task.targetType === 'indicator') {
        await this.generateIndicatorStrategyDraft(prompt, target)
      } else if (task.targetType === 'script') {
        await this.generateScriptStrategyDraft(prompt, target)
      } else if (task.targetType === 'bot') {
        await this.generateBotRecommendation(prompt, target)
      }
      this.pendingAgentTask = null
    },
    isMonitorIntent (text) {
      const value = String(text || '').toLowerCase()
      return /(定时|周期|提醒|通知|监控|跟踪|scheduled|schedule|monitor|alert)/i.test(value) &&
        /(ai|分析|analysis|scan|任务|task)/i.test(value)
    },
    parseMonitorSetup (text) {
      const value = String(text || '')
      const intervalMatch = value.match(/(\d+)\s*(分钟|分|小时|h|hour|hours|min|minute|minutes)/i)
      let interval = null
      if (intervalMatch) {
        const n = Number(intervalMatch[1])
        const unit = String(intervalMatch[2] || '').toLowerCase()
        interval = /小时|h|hour/.test(unit) ? n * 60 : n
      } else if (/每天|每日|daily/i.test(value)) {
        interval = 1440
      }
      const channels = []
      if (/站内|浏览器|browser|site/i.test(value)) channels.push('browser')
      if (/邮件|邮箱|email/i.test(value)) channels.push('email')
      if (/webhook|telegram|tg|飞书|钉钉|discord/i.test(value)) channels.push('webhook')
      const focusMatch = value.match(/(?:重点关注|关注条件|focus)[:：]?\s*([\s\S]+)/i)
      const focus = focusMatch ? focusMatch[1].trim() : value.trim()
      return {
        interval_min: interval,
        notify_channels: Array.from(new Set(channels)),
        focus_conditions: focus || value
      }
    },
    buildMonitorQuestion (target) {
      const label = target && target.symbol ? (target.market + ':' + target.symbol) : (this.isZh ? '当前标的' : 'current symbol')
      return this.isZh
        ? [
            '可以，我先为 **' + label + '** 准备 AI 定时分析任务。',
            '',
            '请补充 3 项信息，我拿到后会生成一份可提交的任务配置：',
            '',
            '1. **周期**：例如 15分钟 / 30分钟 / 1小时 / 4小时 / 每天',
            '2. **通知方式**：站内消息 / 邮件 / Webhook / 只记录不通知',
            '3. **重点关注条件**：例如突破放量、跌破支撑、4H 趋势转强、假突破风险等',
            '',
            '你可以直接这样回复：',
            '',
            '周期：1小时',
            '通知方式：站内消息',
            '重点关注：突破上方阻力且放量提醒；跌破关键支撑提醒；4H 趋势转强/转弱提醒；假突破单独标风险'
          ].join('\n')
        : [
            'Sure. I will prepare an AI scheduled analysis task for **' + label + '**.',
            '',
            'Please provide:',
            '1. Interval: 15m / 30m / 1h / 4h / daily',
            '2. Notification: browser / email / webhook / record only',
            '3. Focus conditions: breakout, support break, 4H trend change, false-break risk, etc.',
            '',
            'Example:',
            'Interval: 1h',
            'Notification: browser',
            'Focus: breakout with volume, support break, 4H trend change, false-break risk'
          ].join('\n')
    },
    buildMonitorDraftMessage (payload) {
      const target = this.normalizeSymbolOption(payload.target || payload)
      const channels = payload.notify_channels || payload.channels || []
      return this.isZh
        ? [
            '## AI 定时分析任务草案',
            '',
            '- 标的：' + target.market + ':' + target.symbol,
            '- 周期：' + this.formatIntervalText(payload.interval_min),
            '- 通知：' + (channels.length ? channels.join(', ') : '只记录不通知'),
            '',
            '### 重点关注',
            payload.focus_conditions || '默认关注趋势、量能、关键价位和风险变化。',
            '',
            '确认无误后，点击下方按钮即可创建任务。'
          ].join('\n')
        : [
            '## AI Scheduled Analysis Draft',
            '',
            '- Symbol: ' + target.market + ':' + target.symbol,
            '- Interval: ' + this.formatIntervalText(payload.interval_min),
            '- Notification: ' + (channels.length ? channels.join(', ') : 'record only'),
            '',
            '### Focus conditions',
            payload.focus_conditions || 'Not specified; use trend, volume, levels, and risk by default.',
            '',
            'Click the action below to create this task in QuantDinger.'
          ].join('\n')
    },
    async handleMonitorAgentMessage (content) {
      const isExistingTask = this.pendingAgentTask && this.pendingAgentTask.type === 'monitor_setup'
      if (!isExistingTask && !this.isMonitorIntent(content)) return false
      const target = this.normalizeSymbolOption((this.pendingAgentTask && this.pendingAgentTask.target) || this.context)
      if (!target || !target.symbol) {
        this.messages.push({
          localId: 'local-' + localId++,
          role: 'assistant',
          content: this.i18nText(
            'aiAssetAnalysis.copilot.monitorMissingSymbol',
            'I can create an AI scheduled analysis task, but no symbol is selected. Choose a data context or mention a symbol like Crypto:BTC/USDT.'
          ),
          meta: this.i18nText('aiAssetAnalysis.copilot.missingSymbolMeta', 'missing symbol'),
          created_at: new Date().toISOString()
        })
        return true
      }
      if (!isExistingTask) {
        this.pendingAgentTask = {
          type: 'monitor_setup',
          target,
          required: ['interval_min', 'notify_channels', 'focus_conditions']
        }
        this.messages.push({
          localId: 'local-' + localId++,
          role: 'assistant',
          content: this.buildMonitorQuestion(target),
          meta: this.isZh ? '等待任务参数' : 'waiting for task parameters',
          created_at: new Date().toISOString()
        })
        return true
      }
      const parsed = this.parseMonitorSetup(content)
      const missing = []
      if (!parsed.interval_min) missing.push(this.isZh ? '周期' : 'interval')
      if (!parsed.notify_channels.length && !/(只记录不通知|不通知|record only|no notification)/i.test(content)) missing.push(this.isZh ? '通知方式' : 'notification')
      if (!parsed.focus_conditions || parsed.focus_conditions.length < 8) missing.push(this.isZh ? '重点关注条件' : 'focus conditions')
      if (missing.length) {
        this.messages.push({
          localId: 'local-' + localId++,
          role: 'assistant',
          content: this.isZh
            ? ('还缺少：' + missing.join('、') + '。\n\n把缺少的信息补上，我会整理最终任务草案。')
            : ('Still missing: ' + missing.join(', ') + '.\n\nSend the missing items and I will prepare the final task draft.'),
          meta: this.isZh ? '参数不完整' : 'incomplete parameters',
          created_at: new Date().toISOString()
        })
        return true
      }
      const payload = {
        target,
        interval_min: parsed.interval_min,
        notify_channels: parsed.notify_channels,
        focus_conditions: parsed.focus_conditions,
        name: 'AI-' + target.symbol + '-' + parsed.interval_min + 'm'
      }
      this.messages.push({
        localId: 'local-' + localId++,
        role: 'assistant',
        content: this.buildMonitorDraftMessage(payload),
        actions: [{
          key: 'create-monitor-' + Date.now(),
          type: 'create_monitor_task',
          icon: 'clock-circle',
          label: this.isZh ? '确认创建任务' : 'Create task',
          payload
        }],
        meta: this.isZh ? '待确认创建' : 'ready to create',
        created_at: new Date().toISOString()
      })
      return true
    },
    async createMonitorFromAction (payload) {
      const rawTarget = payload.target || {
        market: payload.market || payload.selected_market || payload.resolved_market || (this.context && this.context.market),
        symbol: payload.symbol || payload.ticker || payload.code || payload.resolved_symbol || (this.context && this.context.symbol)
      }
      const target = this.normalizeSymbolOption(rawTarget)
      if (!target || !target.symbol) {
        this.$message.warning(this.text.symbolPlaceholder)
        return
      }
      try {
        const interval = Number(payload.interval_min || payload.interval || payload.run_interval_minutes || 240)
        const channels = Array.isArray(payload.notify_channels)
          ? payload.notify_channels
          : (Array.isArray(payload.channels) ? payload.channels : [])
        const res = await addMonitor({
          name: payload.name || ('AI-' + target.symbol + '-' + interval + 'm'),
          position_ids: [],
          monitor_type: 'ai',
          config: {
            run_interval_minutes: interval,
            symbol: target.symbol,
            market: target.market,
            focus_conditions: payload.focus_conditions || payload.focus || '',
            language: this.$store && this.$store.getters ? (this.$store.getters.lang || 'zh-CN') : (this.$i18n ? this.$i18n.locale : 'zh-CN')
          },
          notification_config: { channels },
          is_active: true
        })
        if (!res || res.code === 0) throw new Error((res && res.msg) || this.text.monitorCreated)
        this.$message.success(this.text.monitorCreated)
        this.pendingAgentTask = null
        await this.loadMonitors()
        const message = {
          localId: 'local-' + localId++,
          role: 'assistant',
          content: this.isZh
            ? ('已创建 AI 定时分析任务：\n\n- 标的：' + target.market + ':' + target.symbol + '\n- 周期：' + this.formatIntervalText(interval) + '\n- 通知：' + (channels.length ? channels.join(', ') : '只记录不通知') + '\n\n你可以在右侧 AI 定时分析任务面板中暂停、删除或查看任务。')
            : ('AI scheduled analysis task created:\n\n- Symbol: ' + target.market + ':' + target.symbol + '\n- Interval: ' + this.formatIntervalText(interval) + '\n- Notifications: ' + (channels.length ? channels.join(', ') : 'record only') + '\n\nYou can pause, delete, or inspect it in the AI Scheduled Analysis panel.'),
          meta: this.isZh ? '任务已创建' : 'task created',
          created_at: new Date().toISOString()
        }
        this.messages.push(message)
        await this.persistCopilotMessage(message, 'monitor_created')
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || 'Create monitor failed')
      }
    },
    cleanMarkdownCodeBlocks (code) {
      if (!code || typeof code !== 'string') return code || ''
      let c = code.trim()
      if (c.startsWith('```python')) c = c.slice(9)
      else if (c.startsWith('```')) c = c.slice(3)
      if (c.endsWith('```')) c = c.slice(0, -3)
      return c.trim()
    },
    inferSymbolFromText (text) {
      const value = String(text || '').toUpperCase()
      const pair = value.match(/\b[A-Z0-9]{2,12}\/[A-Z0-9]{2,12}\b/)
      if (pair) return { market: 'Crypto', symbol: pair[0] }
      const usdAsset = value.match(/\b([A-Z]{2,10})-USD\b/)
      if (usdAsset) {
        const base = usdAsset[1]
        if (['BTC', 'ETH', 'SOL', 'TON', 'HYPE', 'DOGE', 'XRP', 'BNB', 'ADA', 'AVAX'].includes(base)) {
          return { market: 'Crypto', symbol: `${base}/USDT` }
        }
        return { market: 'USStock', symbol: base }
      }
      const marketPair = value.match(/\b(CRYPTO|USSTOCK|HKSTOCK|CNSTOCK|FOREX|FUTURES):([A-Z0-9./_-]{2,24})\b/)
      if (marketPair) return { market: marketPair[1], symbol: marketPair[2] }
      const cnCode = value.match(/(?:^|[^\d])([036]\d{5})(?:[^\d]|$)/)
      if (cnCode) return { market: 'CNStock', symbol: cnCode[1] }
      const hkCode = value.match(/(?:^|[^\d])(\d{5})(?:[^\d]|$)/)
      if (hkCode) return { market: 'HKStock', symbol: hkCode[1] }
      return null
    },
    commonSymbolAliases () {
      return [
        { keys: ['英伟达', '輝達', 'nvidia', 'nvda'], market: 'USStock', symbol: 'NVDA', name: 'NVIDIA' },
        { keys: ['特斯拉', 'tesla', 'tsla'], market: 'USStock', symbol: 'TSLA', name: 'Tesla' },
        { keys: ['苹果', '蘋果', 'apple', 'aapl'], market: 'USStock', symbol: 'AAPL', name: 'Apple' },
        { keys: ['微软', '微軟', 'microsoft', 'msft'], market: 'USStock', symbol: 'MSFT', name: 'Microsoft' },
        { keys: ['谷歌', 'google', 'alphabet', 'googl'], market: 'USStock', symbol: 'GOOGL', name: 'Alphabet' },
        { keys: ['亚马逊', '亞馬遜', 'amazon', 'amzn'], market: 'USStock', symbol: 'AMZN', name: 'Amazon' },
        { keys: ['meta', 'facebook', '脸书', '臉書'], market: 'USStock', symbol: 'META', name: 'Meta' },
        { keys: ['宁德时代', '寧德時代', 'catl'], market: 'CNStock', symbol: '300750', name: '宁德时代' },
        { keys: ['茅台', '贵州茅台', '貴州茅台'], market: 'CNStock', symbol: '600519', name: '贵州茅台' },
        { keys: ['比特币', '比特幣', 'bitcoin', 'btc'], market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' },
        { keys: ['以太坊', 'ethereum', 'eth'], market: 'Crypto', symbol: 'ETH/USDT', name: 'Ethereum' },
        { keys: ['黄金', '黃金', 'gold', 'xau'], market: 'Forex', symbol: 'XAUUSD', name: 'Gold/USD' }
      ]
    },
    normalizeSearchText (text) {
      return String(text || '')
        .replace(/[，。！？、；：,.!?;:"'`~()[\]{}<>]/g, ' ')
        .replace(/\b(analyze|analysis|stock|price|trend|today|current|please|for|of|the)\b/gi, ' ')
        .replace(/请|幫|帮|我|看|分析|一下|当前|今天|现在|目前|股票|股价|价格|多少钱|多少|走势|趋势|这个|那个|的|是|如何|怎么样|怎麼樣|能不能|可以|查|查询|行情/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
    },
    symbolSearchCandidates (message) {
      const raw = String(message || '').trim()
      const cleaned = this.normalizeSearchText(raw)
      const candidates = []
      ;[cleaned, raw].forEach(value => {
        if (value && value.length >= 2 && value.length <= 32) candidates.push(value)
      })
      const codeTokens = raw.match(/[A-Za-z][A-Za-z0-9._-]{1,12}/g) || []
      codeTokens.forEach(x => candidates.push(x))
      const zhTokens = raw.match(/[\u4e00-\u9fa5]{2,12}/g) || []
      zhTokens.forEach(x => {
        const y = this.normalizeSearchText(x)
        if (y) candidates.push(y)
      })
      return Array.from(new Set(candidates.map(x => String(x).trim()).filter(x => x.length >= 2))).slice(0, 5)
    },
    findLocalSymbolMatch (message) {
      const raw = String(message || '')
      const lower = raw.toLowerCase()
      const alias = this.commonSymbolAliases().find(item => item.keys.some(key => lower.includes(String(key).toLowerCase())))
      if (alias) return this.normalizeSymbolOption(alias)
      const watch = (this.watchlist || []).find(item => {
        const normalized = this.normalizeSymbolOption(item)
        if (!normalized) return false
        const symbol = String(normalized.symbol || '').toLowerCase()
        const name = String(normalized.name || '').toLowerCase()
        return (symbol && lower.includes(symbol)) || (name && lower.includes(name))
      })
      return watch ? this.normalizeSymbolOption(watch) : null
    },
    async resolveMessageSymbol (message = '') {
      const explicit = this.inferSymbolFromText(message)
      if (explicit) return explicit
      const local = this.findLocalSymbolMatch(message)
      if (local) return local
      const candidates = this.symbolSearchCandidates(message)
      for (const keyword of candidates) {
        try {
          const res = await searchSymbols({ keyword, limit: 6 })
          const data = res.data || {}
          const list = Array.isArray(data) ? data : (data.results || data.symbols || data.items || [])
          const normalized = list.map(x => this.normalizeSymbolOption(x)).filter(Boolean)
          if (normalized.length) return normalized[0]
        } catch (_) {}
      }
      return null
    },
    buildChatContext (message = '', resolvedSymbol = null) {
      const recent = (this.messages || [])
        .filter(msg => msg && msg.content)
        .slice(-8)
        .map(msg => ({
          role: msg.role,
          meta: msg.meta || '',
          content: String(msg.content || '').slice(0, 8000)
        }))
      const locked = resolvedSymbol && resolvedSymbol.locked ? this.normalizeSymbolOption(resolvedSymbol) : null
      const selected = this.normalizeSymbolOption(this.context)
      const mentioned = this.inferSymbolFromText(message)
      const resolved = locked ? locked : this.normalizeSymbolOption(resolvedSymbol)
      const active = locked || mentioned || resolved || selected
      const activePrice = active ? this.priceFor(active) : null
      const macroContext = this.macroContextForMessage(message)
      return {
        client_time: new Date().toISOString(),
        market: active ? active.market : '',
        symbol: active ? active.symbol : '',
        name: active ? (active.name || '') : '',
        selected_market: selected ? selected.market : '',
        selected_symbol: selected ? selected.symbol : '',
        mentioned_market: !locked && (mentioned || resolved) ? (mentioned || resolved).market : '',
        mentioned_symbol: !locked && (mentioned || resolved) ? (mentioned || resolved).symbol : '',
        ignored_mentioned_market: locked && mentioned ? mentioned.market : '',
        ignored_mentioned_symbol: locked && mentioned ? mentioned.symbol : '',
        resolved_market: resolved ? resolved.market : '',
        resolved_symbol: resolved ? resolved.symbol : '',
        locked_market: locked ? locked.market : '',
        locked_symbol: locked ? locked.symbol : '',
        symbol_context_mode: locked ? 'locked_selected_context' : (mentioned ? 'mentioned_in_message' : (resolved ? 'resolved_from_message' : (selected ? 'optional_selected_context' : 'auto_infer'))),
        allow_symbol_switch: !locked,
        locked_symbol_policy: locked
          ? (this.isZh
              ? `本次任务已锁定到 ${locked.market}:${locked.symbol}。即使用户文本或提示词中出现其他示例标的，也必须以 locked_market/locked_symbol 为准；只有用户明确要求切换标的时才提示重新选择数据上下文。`
              : `This task is locked to ${locked.market}:${locked.symbol}. Even if the text contains another example symbol, use locked_market/locked_symbol as the target unless the user explicitly asks to switch.`)
          : '',
        use_system_data_source: true,
        active_price: activePrice || null,
        agent_task: this.pendingAgentTask ? {
          type: this.pendingAgentTask.type,
          targetType: this.pendingAgentTask.targetType,
          target: this.pendingAgentTask.target,
          workflow: this.pendingAgentTask.workflow
        } : null,
        user_memories: (this.userMemories || []).slice(0, 12),
        economic_calendar_context: macroContext.events,
        macro_data_policy: macroContext.enabled
          ? 'For macro/economic-data questions, inspect economic_calendar_context and system data before answering. If exact actual/forecast/previous values are missing, say which field is missing and guide the user to the required data source instead of claiming the system cannot help.'
          : '',
        data_source_policy: this.isZh
          ? '用户可能不会手动选择数据源。请优先根据自然语言自动识别市场和标的，并结合系统行情、自选列表和市场上下文回答；如果实时数据缺失，请明确说明缺口，同时给出可执行的观察方法，不要直接停止回答。'
          : 'Users may not manually choose a data source. Infer the market and symbol from natural language first, then use system data/watchlist/market context. If live data is missing, state the gap and still provide actionable next steps instead of stopping.',
        copilot_recent_messages: recent
      }
    },
    async handleQuickPrompt (item) {
      if (!item) return
      const activeItem = { ...item, prompt: await this.resolveSkillPrompt(item) }
      const target = this.selectedContextTarget()
      const key = String((activeItem.key || activeItem.skillId || activeItem.id) || '').toLowerCase()
      const needsTarget = this.quickTaskRequiresSymbol(activeItem)
      if (needsTarget) {
        if (!target) {
          this.promptSelectSymbolFirst()
          return
        }
        if (key === 'indicator_strategy') {
          this.pendingAgentTask = {
            type: 'strategy_design',
            targetType: 'indicator',
            target,
            workflow: 'QuantDinger Indicator IDE',
            originalPrompt: ''
          }
          this.usePrompt(this.buildLockedQuickPrompt(activeItem, target), { contextLock: target })
          return
        }
        if (key === 'scheduled_analysis' || key === 'monitor') {
          this.beginMonitorSetup(target)
          return
        }
        if (key === 'opportunity_radar' || key === 'radar') {
          this.usePrompt(this.buildLockedQuickPrompt(activeItem, target), { contextLock: target })
          return
        }
      }
      if (activeItem.action === 'analysis') {
        this.runProfessionalAnalysis()
        return
      }
      if (activeItem.action === 'strategy') {
        this.strategyFlowVisible = true
        return
      }
      if (activeItem.action === 'addWatch') {
        this.openAddWatchModal()
        return
      }
      if (activeItem.action === 'monitor') {
        this.pendingAgentTask = null
        this.usePrompt(activeItem.prompt)
        return
      }
      if (activeItem.action === 'route') {
        this.runMessageAction(activeItem)
        return
      }
      this.usePrompt(activeItem.prompt)
    },
    async resolveSkillPrompt (item) {
      if (!item || !item.skillId) return item ? item.prompt : ''
      try {
        const res = await getAiSkillPrompt(item.skillId, {
          language: this.isZh ? 'zh-CN' : 'en-US',
          context: this.buildMessageContext()
        })
        const data = res.data || {}
        return data.prompt || item.prompt || ''
      } catch (_) {
        return item.prompt || ''
      }
    },
    async runProfessionalAnalysis () {
      const target = this.normalizeSymbolOption(this.context)
      if (!target || !target.symbol) {
        this.usePrompt(this.buildAnalysisPrompt(null))
        this.$message.info(this.isZh ? '已填入诊断模板，请补充标的后发送。' : 'Analysis prompt inserted. Add a symbol, then send it.')
        return
      }
      const userMsg = {
        localId: `local-${localId++}`,
        role: 'user',
        content: this.isZh
          ? `诊断 ${target.market}:${target.symbol}`
          : `Diagnose ${target.market}:${target.symbol}`,
        created_at: new Date().toISOString()
      }
      const assistantMsg = {
        localId: `local-${localId++}`,
        role: 'assistant',
        content: '',
        meta: this.text.analysisRunning,
        reportLoading: true,
        reportTarget: target,
        created_at: new Date().toISOString()
      }
      this.messages.push(userMsg, assistantMsg)
      this.scrollToBottom()
      this.sending = true
      try {
        const result = await this.fetchProfessionalAnalysis(target)
        assistantMsg.report = result
        assistantMsg.reportLoading = false
        assistantMsg.reportError = ''
        assistantMsg.meta = this.text.analysisComplete
        assistantMsg.actions = this.reportActions(assistantMsg)
        await this.persistCopilotMessage(userMsg, 'fast_analysis_user')
        await this.persistCopilotMessage(assistantMsg, 'fast_analysis_report')
        this.loadSessions()
      } catch (e) {
        assistantMsg.reportLoading = false
        assistantMsg.reportError = (e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || (this.isZh ? '分析失败' : 'Analysis failed')
        assistantMsg.reportErrorTone = this.isInProgressError(e) ? 'warning' : 'error'
        assistantMsg.meta = this.isZh ? '分析失败' : 'analysis failed'
      } finally {
        this.sending = false
        this.scrollToBottom()
      }
    },
    async fetchProfessionalAnalysis (target) {
      const res = await fastAnalyze({
        market: target.market,
        symbol: target.symbol,
        language: this.$i18n ? this.$i18n.locale : 'zh-CN',
        timeframe: '1D'
      })
      if (!res || res.code === 0) {
        const err = new Error((res && res.msg) || (this.isZh ? '分析失败' : 'Analysis failed'))
        err.response = { data: res || {} }
        throw err
      }
      const data = res.data || {}
      return {
        ...data,
        market: data.market || target.market,
        symbol: data.symbol || target.symbol
      }
    },
    isInProgressError (e) {
      const data = e && e.response && e.response.data
      const msg = String((data && data.msg) || (e && e.message) || '')
      return msg.toLowerCase().includes('in progress') || msg.includes('正在进行')
    },
    reportId (msg) {
      return String((msg && (msg.localId || msg.id)) || '')
    },
    reportActions (msg) {
      const id = this.reportId(msg)
      return [
        {
          key: `export-report-${id}`,
          type: 'export_report_pdf',
          icon: 'download',
          label: this.isZh ? '导出 PDF' : 'Export PDF',
          payload: { reportId: id }
        },
        {
          key: `ask-report-${id}`,
          type: 'ask_about_report',
          icon: 'message',
          label: this.isZh ? '继续追问' : 'Ask follow-up',
          payload: { reportId: id }
        }
      ]
    },
    async retryProfessionalAnalysis (msg) {
      const target = msg && msg.reportTarget
      if (!target || !target.symbol) return
      msg.reportLoading = true
      msg.reportError = ''
      msg.meta = this.text.analysisRunning
      this.sending = true
      try {
        msg.report = await this.fetchProfessionalAnalysis(target)
        msg.reportLoading = false
        msg.actions = this.reportActions(msg)
        msg.meta = this.text.analysisComplete
      } catch (e) {
        msg.reportLoading = false
        msg.reportError = (e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || (this.isZh ? '分析失败' : 'Analysis failed')
        msg.reportErrorTone = this.isInProgressError(e) ? 'warning' : 'error'
      } finally {
        this.sending = false
      }
    },
    handleReportGenerateStrategy (result) {
      const market = result.market || (this.context && this.context.market) || ''
      const symbol = result.symbol || (this.context && this.context.symbol) || ''
      const decision = result.decision || 'HOLD'
      const tp = result.trading_plan || {}
      const query = {
        mode: 'create',
        market,
        symbol,
        from_analysis: '1',
        decision,
        entry_price: tp.entry_price || tp.entryPrice || '',
        stop_loss: tp.stop_loss || tp.stopLoss || '',
        take_profit: tp.take_profit || tp.takeProfit || ''
      }
      Object.keys(query).forEach(k => { if (!query[k] && query[k] !== 0) delete query[k] })
      this.$router.push({ path: '/strategy-live', query })
    },
    handleReportGoBacktest (result) {
      const market = result.market || (this.context && this.context.market) || ''
      const symbol = result.symbol || (this.context && this.context.symbol) || ''
      this.$router.push({ path: '/indicator-ide', query: { market, symbol } })
    },
    async exportReportPdf (reportId) {
      if (!reportId) return
      const msg = (this.messages || []).find(item => this.reportId(item) === String(reportId))
      if (!msg || !msg.report) {
        this.$message.warning(this.isZh ? '没有可导出的报告数据' : 'No report data to export')
        return
      }
      try {
        const blob = await exportChatReportPdf({
          report: msg.report,
          target: msg.reportTarget || this.context || {},
          language: (this.$i18n && this.$i18n.locale) || (this.isZh ? 'zh-CN' : 'en-US')
        })
        const fileBlob = blob instanceof Blob ? blob : new Blob([blob], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(fileBlob)
        const link = document.createElement('a')
        link.href = url
        link.download = this.reportPdfFilename(msg)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.setTimeout(() => window.URL.revokeObjectURL(url), 1000)
      } catch (e) {
        this.$message.error((e && (e.backendMessage || e.message)) || (this.isZh ? 'PDF 导出失败' : 'PDF export failed'))
      }
    },
    reportPdfFilename (msg) {
      const report = (msg && msg.report) || {}
      const target = (msg && msg.reportTarget) || this.context || {}
      const symbol = String(report.symbol || target.symbol || 'report').replace(/[\\/:*?"<>|]+/g, '_')
      const date = new Date().toISOString().slice(0, 10)
      return `QuantDinger_${symbol}_${date}.pdf`
    },
    askAboutReport (reportId) {
      const msg = (this.messages || []).find(item => this.reportId(item) === String(reportId))
      const target = (msg && msg.reportTarget) || this.context
      const label = target && target.symbol ? `${target.market}:${target.symbol}` : (this.isZh ? '这份报告' : 'this report')
      this.usePrompt(this.isZh
        ? `基于刚才 ${label} 的诊断报告，请继续解释：`
        : `Based on the diagnosis report for ${label}, explain further:`
      )
    },
    buildAnalysisPrompt (target) {
      const symbol = target && target.symbol ? `${target.market}:${target.symbol}` : (this.isZh ? '用户指定的标的' : 'the user-selected symbol')
      return this.isZh
        ? [
            `请基于系统数据源，对 ${symbol} 做一份可执行的交易分析。`,
            '',
            '要求：',
            '1. 明确说明当前价格、周期、数据时间；没有数据就直接说明缺口，不要编造。',
            '2. 从趋势、量能、关键支撑阻力、资金面、风险五个角度分析。',
            '3. 给出偏多、震荡、偏空三种情景下的触发条件。',
            '4. 给出具体操作建议：观察位、入场确认、止损失效条件、止盈/减仓思路。',
            '5. 结论要有优先级，不要只给通用框架。'
          ].join('\n')
        : [
            `Use the system data source to produce an actionable trading analysis for ${symbol}.`,
            '',
            'Requirements:',
            '1. State current price, timeframe, and data timestamp. If data is unavailable, say so instead of inventing it.',
            '2. Analyze trend, volume, key support/resistance, capital flow, and risk.',
            '3. Give bullish, range-bound, and bearish trigger conditions.',
            '4. Provide concrete actions: observation levels, entry confirmation, invalidation stop, and take-profit/reduction logic.',
            '5. Prioritize the conclusion; do not return only a generic framework.'
          ].join('\n')
    },
    formatFastAnalysisMarkdown (result, target) {
      const decision = result.final_decision || result.decision || result.signal || 'HOLD'
      const confidence = result.confidence != null ? `${result.confidence}%` : '--'
      const price = result.current_price || (result.market_data && result.market_data.current_price) || result.price || '--'
      const entry = result.entry_price || result.suggested_entry || '--'
      const stop = result.stop_loss || (result.trading_levels && result.trading_levels.stop_loss) || '--'
      const take = result.take_profit || (result.trading_levels && result.trading_levels.take_profit) || '--'
      const reasons = result.key_reasons || result.reasons || []
      const risks = result.risks || result.risk_factors || []
      const detailed = result.detailed_analysis || result.analysis || {}
      const lines = [
        `## ${target.symbol} ${this.isZh ? '专业 AI 分析报告' : 'Professional AI Analysis Report'}`,
        '',
        `- ${this.isZh ? '结论' : 'Decision'}: **${decision}**`,
        `- ${this.isZh ? '置信度' : 'Confidence'}: **${confidence}**`,
        `- ${this.isZh ? '当前价' : 'Current Price'}: ${price}`,
        `- ${this.isZh ? '参考入场' : 'Reference Entry'}: ${entry}`,
        `- ${this.isZh ? '止损' : 'Stop Loss'}: ${stop}`,
        `- ${this.isZh ? '止盈' : 'Take Profit'}: ${take}`,
        ''
      ]
      if (result.summary || result.consensus_summary) {
        lines.push(`### ${this.isZh ? '综合判断' : 'Summary'}`, String(result.summary || result.consensus_summary), '')
      }
      if (Array.isArray(reasons) && reasons.length) {
        lines.push(`### ${this.isZh ? '关键理由' : 'Key Reasons'}`)
        reasons.slice(0, 6).forEach(x => lines.push(`- ${x}`))
        lines.push('')
      }
      if (detailed && typeof detailed === 'object') {
        const sections = [
          ['technical_analysis', this.isZh ? '技术面' : 'Technical'],
          ['fundamental_analysis', this.isZh ? '基本面/资金面' : 'Fundamental / Flow'],
          ['sentiment_analysis', this.isZh ? '情绪面' : 'Sentiment']
        ]
        sections.forEach(([key, label]) => {
          if (detailed[key]) lines.push(`### ${label}`, String(detailed[key]), '')
        })
      } else if (detailed) {
        lines.push(`### ${this.isZh ? '详细分析' : 'Detailed Analysis'}`, String(detailed), '')
      }
      if (Array.isArray(risks) && risks.length) {
        lines.push(`### ${this.isZh ? '风险点' : 'Risks'}`)
        risks.slice(0, 6).forEach(x => lines.push(`- ${x}`))
        lines.push('')
      }
      return lines.join('\n')
    },
    buildStrategyPrompt (targetKey, target) {
      const targetText = target && target.symbol
        ? `${target.market}:${target.symbol}`
        : this.i18nText(
          'aiAssetAnalysis.copilot.strategySymbolPlaceholder',
          '[enter symbol here, e.g. Crypto:BTC/USDT or CNStock:300750]'
        )
      const commonZh = [
        `请为 ${targetText} 设计一个策略。`,
        '',
        '我的想法/偏好：',
        '- 交易周期：',
        '- 风险偏好：',
        '- 我希望利用的信号或逻辑：',
        '- 不希望出现的行为：',
        '',
        '如果信息足够，请直接生成可运行草稿；缺失参数用保守默认值，并把默认值和可调项列清楚。'
      ]
      const commonEn = [
        `Design a strategy for ${targetText}.`,
        '',
        'My idea / preferences:',
        '- Timeframe:',
        '- Risk profile:',
        '- Signals or logic I want to use:',
        '- Behaviors I want to avoid:',
        '',
        'If there is enough information, generate a runnable draft now. Use conservative defaults for missing parameters and clearly list defaults and tunable items.'
      ]
      if (targetKey === 'indicator') {
        return this.isZh
          ? [...commonZh, '', '目标类型：策略研发。当前优先生成可落地到策略 IDE 的指标策略草稿，需要适合在 K 线图展示、回测，并说明参数、买卖信号、止损止盈和失效条件。'].join('\n')
          : [...commonEn, '', 'Target type: Strategy Lab. Prefer a Strategy IDE-ready indicator strategy draft that supports chart display and backtesting, with parameters, buy/sell signals, stop/take-profit, and invalidation conditions.'].join('\n')
      }
      if (targetKey === 'script') {
        return this.isZh
          ? [...commonZh, '', '目标类型：脚本策略。需要适合 Python ScriptStrategy，包含状态管理、下单逻辑、风控参数、异常处理和日志输出。'].join('\n')
          : [...commonEn, '', 'Target type: Script Strategy. It should fit Python ScriptStrategy with state management, order logic, risk parameters, error handling, and logging.'].join('\n')
      }
      return this.isZh
        ? [...commonZh, '', '目标类型：模板策略。请先判断更适合网格、趋势、DCA、马丁或其他模板策略类型，并解释原因和关键参数。'].join('\n')
        : [...commonEn, '', 'Target type: Template Strategy. First decide whether grid, trend, DCA, martingale, or another template strategy type fits best, then explain why and list key parameters.'].join('\n')
    },
    agentTargetFromPlan (plan, fallbackTarget) {
      const entities = plan && plan.entities ? plan.entities : {}
      const target = this.normalizeSymbolOption({
        market: entities.market || (fallbackTarget && fallbackTarget.market),
        symbol: entities.symbol || (fallbackTarget && fallbackTarget.symbol),
        name: entities.name || (fallbackTarget && fallbackTarget.name)
      })
      return target || this.normalizeSymbolOption(fallbackTarget)
    },
    strategyTargetTypeFromPlan (plan) {
      const targetType = String(plan && plan.target_type ? plan.target_type : '').toLowerCase()
      const workflow = String(plan && plan.workflow ? plan.workflow : '').toLowerCase()
      if (targetType === 'bot' || workflow === 'trading_bot') return 'bot'
      if (targetType === 'script' || workflow === 'script_strategy') return 'script'
      return 'indicator'
    },
    buildExecutableStrategyPrompt (plan, message, target) {
      const entities = plan && plan.entities ? plan.entities : {}
      const timeframe = entities.timeframe || ''
      const template = entities.strategy_template || ''
      const workflow = plan && plan.workflow ? plan.workflow : 'indicator_ide'
      const memoryLines = (this.userMemories || [])
        .slice(0, 8)
        .map(item => `- ${item.title || item.category}: ${item.content}`)
        .join('\n')
      return [
        'This is an execution task, not a consulting answer.',
        'Generate the runnable QuantDinger strategy artifact now.',
        `Workflow: ${workflow}`,
        `Target: ${target.market}:${target.symbol}`,
        timeframe ? `Timeframe: ${timeframe}` : 'Timeframe: choose a conservative default if the user did not specify it.',
        template ? `Reference strategy/template: ${template}` : '',
        '',
        'Execution rules:',
        '- Do not ask for confirmation when the target, timeframe, and strategy idea can be inferred.',
        '- Use conservative defaults for missing parameters and document them in the output.',
        '- Code comments must be English.',
        '- Stay inside QuantDinger native workflows.',
        '- For Indicator IDE, generate runnable QuantDinger Indicator IDE Python code, not Pine Script.',
        '- For Indicator IDE, execution must use df four-way boolean columns; output signals are chart markers only.',
        '- For Indicator IDE chart annotations, you may use output.layers for zones, support/resistance lines, and labels when it improves readability.',
        '- For Script Strategy, generate a Python ScriptStrategy draft that can be validated by QuantDinger.',
        '- For Template Strategy, return a concrete template strategy plan with parameters; do not auto-start live trading.',
        '- Include verification steps: open in QuantDinger, run backtest, inspect drawdown/win rate/trades, then save manually.',
        memoryLines ? `\nUser memory:\n${memoryLines}` : '',
        '',
        'Original user request:',
        message || ''
      ].filter(Boolean).join('\n')
    },
    async classifyAgentPlan (content, attachments, contextLock = null) {
      const resolvedSymbol = contextLock || await this.resolveMessageSymbol(content)
      const context = this.buildChatContext(content, resolvedSymbol)
      const res = await classifyAgentIntent({
        message: content,
        attachments,
        context,
        language: this.$i18n ? this.$i18n.locale : 'zh-CN'
      })
      const plan = res && res.data ? res.data : null
      return { plan, resolvedSymbol }
    },
    async handleBackendAgentIntent (content, attachments, contextLock = null) {
      let plan = null
      let resolvedSymbol = null
      try {
        const classified = await this.classifyAgentPlan(content, attachments, contextLock)
        plan = classified.plan
        resolvedSymbol = classified.resolvedSymbol
      } catch (_) {
        return false
      }
      if (!plan || !plan.should_execute || plan.intent !== 'strategy_build') return false
      const target = this.agentTargetFromPlan(plan, contextLock || resolvedSymbol || this.context)
      if (!target || !target.symbol) {
        this.messages.push({
          localId: `local-${localId++}`,
          role: 'assistant',
          content: this.i18nText(
            'aiAssetAnalysis.copilot.strategyMissingSymbol',
            'I classified this as a strategy creation task, but the target symbol is missing. Please provide a symbol such as `Crypto:BTC/USDT`, `USStock:SPCX`, or `CNStock:300750`.'
          ),
          meta: 'agent_intent:missing_symbol',
          created_at: new Date().toISOString()
        })
        return true
      }
      this.context.market = target.market
      this.context.symbol = target.symbol
      this.selectedSymbolValue = this.symbolOptionValue(target)
      this.symbolOptions = [target].concat(this.symbolOptions || [])
      const targetType = this.strategyTargetTypeFromPlan(plan)
      const prompt = this.buildExecutableStrategyPrompt(plan, content, target)
      this.pendingAgentTask = {
        type: 'strategy_design',
        targetType,
        target,
        workflow: plan.workflow,
        originalPrompt: content,
        agentIntent: plan
      }
      if (targetType === 'script') {
        await this.generateScriptStrategyDraft(prompt, target)
      } else if (targetType === 'bot') {
        await this.generateBotRecommendation(prompt, target)
      } else {
        await this.generateIndicatorStrategyDraft(prompt, target)
      }
      this.pendingAgentTask = null
      return true
    },
    async startStrategyFlow (targetKey) {
      const target = this.normalizeSymbolOption(this.context)
      this.strategyFlowVisible = false
      this.pendingAgentTask = {
        type: 'strategy_design',
        targetType: targetKey,
        target,
        workflow: targetKey === 'indicator'
          ? 'QuantDinger Indicator IDE'
          : (targetKey === 'script' ? 'QuantDinger Python ScriptStrategy' : 'QuantDinger Template Strategy'),
        originalPrompt: ''
      }
      this.usePrompt(this.buildStrategyPrompt(targetKey, target))
      this.$message.info(this.isZh ? '已填入策略需求模板，你可以继续补充想法后发送。' : 'Strategy prompt inserted. Add your idea, then send it.')
      return
      if (!target || !target.symbol) {
        this.$message.warning(this.text.symbolPlaceholder)
        return
      }
      this.strategyFlowVisible = false
      const prompt = this.isZh
        ? `请基于 ${target.market}:${target.symbol} 生成一个稳健、可回测、带风控参数的策略。说明适用市场、入场/出场、止损止盈和失效条件。`
        : `Generate a robust, backtestable strategy for ${target.market}:${target.symbol}, including risk parameters, entries/exits, stop/take profit, and invalidation.`
      if (targetKey === 'indicator') {
        await this.generateIndicatorStrategyDraft(prompt, target)
        return
      }
      if (targetKey === 'indicator') {
        this.$confirm({
          title: this.text.indicatorStrategy,
          content: this.isZh ? '我会跳转到策略 IDE，你可以在图表与回测面板里继续运行。' : 'Open Strategy IDE so you can run it in the chart and backtest workspace.',
          okText: this.text.openTargetPage,
          cancelText: this.text.cancel,
          onOk: () => this.$router.push({ path: '/indicator-ide', query: { symbol: target.symbol, market: target.market } })
        })
        return
      }
      if (targetKey === 'script') {
        await this.generateScriptStrategyDraft(prompt, target)
        return
      }
      if (targetKey === 'bot') {
        await this.generateBotRecommendation(prompt, target)
      }
    },
    buildNativeStrategyGenerationPrompt (targetType, prompt, target) {
      const memoryLines = (this.userMemories || [])
        .slice(0, 8)
        .map(item => `- ${item.title || item.category}: ${item.content}`)
        .join('\n')
      const workflow = targetType === 'indicator'
        ? 'QuantDinger Indicator IDE'
        : (targetType === 'script' ? 'QuantDinger Python ScriptStrategy' : 'QuantDinger Template Strategy')
      const hardRules = [
        `Workflow: ${workflow}`,
        `Target: ${target && target.market ? target.market : ''}:${target && target.symbol ? target.symbol : ''}`,
        '',
        'Hard rules:',
        '- This is an execution task, not a consulting answer. Produce the runnable artifact now.',
        '- Do not ask the user to paste templates or confirm obvious defaults.',
        '- Generate only for the QuantDinger workflow above.',
        '- Do not output Pine Script, TradingView-only code, MQL, or code for another platform.',
        '- Code comments must be English.',
        '- Include risk parameters, invalidation, and how the user should verify it in QuantDinger.',
        '- If a required assumption is missing, choose conservative defaults and state them.',
        '',
        memoryLines ? `[User memory]\n${memoryLines}\n` : '',
        '[User requirement]',
        prompt || ''
      ]
      if (targetType === 'indicator') {
        hardRules.splice(
          6,
          0,
          '- Indicator IDE output must be runnable in QuantDinger Indicator IDE and suitable for chart display/backtest.',
          '- Indicator IDE execution must use df four-way boolean columns: open_long, close_long, open_short, close_short.',
          '- output.signals is chart-only. It must never be the only source of backtest/live orders.',
          '- You may add output.layers for K-line zones, support/resistance lines, BOS/CHoCH labels, invalidation ranges, or premium/discount areas. Keep overlays sparse.'
        )
      } else if (targetType === 'script') {
        hardRules.splice(6, 0, '- Script output must be a Python strategy draft for QuantDinger Script Strategy.')
      } else {
        hardRules.splice(6, 0, '- Template strategy output must recommend a QuantDinger template strategy type and concrete parameters.')
      }
      return hardRules.join('\n')
    },
    async generateIndicatorStrategyDraft (prompt, target) {
      this.generatingStrategy = true
      const assistantMsg = {
        localId: `local-${localId++}`,
        role: 'assistant',
        content: this.isZh ? '正在生成策略研发草稿...' : 'Generating Strategy Lab draft...',
        meta: 'indicator_strategy'
      }
      this.messages.push(assistantMsg)
      this.scrollToBottom()
      try {
        const agentPrompt = this.buildNativeStrategyGenerationPrompt('indicator', prompt, target)
        const token = this.getAccessToken()
        const language = this.$i18n ? this.$i18n.locale : 'zh-CN'
        const response = await fetch('/api/indicator/aiGenerate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: token ? `Bearer ${token}` : '',
            'Access-Token': token || '',
            Token: token || '',
            'X-App-Lang': language,
            'Accept-Language': language
          },
          credentials: 'include',
          body: JSON.stringify({ prompt: agentPrompt })
        })
        if (!response.ok || !response.body) throw new Error(`Indicator AI ${response.status}`)
        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        let generatedCode = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''
          for (const part of parts) {
            if (!part.trim() || !part.startsWith('data: ')) continue
            const data = part.substring(6)
            if (data === '[DONE]') continue
            const json = JSON.parse(data)
            if (json.error) throw new Error(json.error)
            if (json.content) {
              generatedCode += json.content
              const code = this.cleanMarkdownCodeBlocks(generatedCode)
              assistantMsg.content = [
                `## ${target.symbol} ${this.text.indicatorStrategy}`,
                '',
                this.isZh ? '已生成策略研发草稿。你可以继续在本会话里要求我修改入场、出场、风控或参数，满意后再去策略 IDE 运行。' : 'A Strategy Lab draft is ready. Keep refining entries, exits, risk controls, or parameters here, then open Strategy IDE when you are satisfied.',
                '',
                '```python',
                code,
                '```'
              ].join('\n')
              this.scrollToBottom()
            }
          }
        }
        const code = this.cleanMarkdownCodeBlocks(generatedCode)
        if (!code) throw new Error('Indicator AI returned empty code')
        assistantMsg.meta = this.text.strategyGenerated
        assistantMsg.actions = [{
          key: 'open-indicator-ide',
          group: 'strategy_workflow',
          icon: 'line-chart',
          label: this.isZh ? '去策略 IDE 运行' : 'Open Strategy IDE',
          path: '/indicator-ide',
          storageKey: 'qd_copilot_indicator_code',
          storageValue: code,
          query: { aiDraft: '1', symbol: target.symbol, market: target.market }
        }]
        await this.persistCopilotMessage(assistantMsg, 'indicator_strategy')
      } catch (e) {
        assistantMsg.content = `${this.text.chatUnavailable}\n\n${(e && e.message) || ''}`
      } finally {
        this.generatingStrategy = false
        this.scrollToBottom()
      }
    },
    async generateScriptStrategyDraft (prompt, target) {
      this.generatingStrategy = true
      const assistantMsg = {
        localId: `local-${localId++}`,
        role: 'assistant',
        content: this.isZh ? '正在生成脚本策略草稿...' : 'Generating script strategy draft...',
        meta: 'strategy_build'
      }
      this.messages.push(assistantMsg)
      this.scrollToBottom()
      try {
        const agentPrompt = this.buildNativeStrategyGenerationPrompt('script', prompt, target)
        const res = await aiGenerateStrategy({ prompt: agentPrompt, intent: 'generate_code' })
        if (!res || !res.code) throw new Error((res && res.msg) || 'AI generation failed')
        sessionStorage.setItem('qd_copilot_script_strategy_code', res.code)
        assistantMsg.content = [
          `## ${target.symbol} ${this.text.scriptStrategy}`,
          '',
          this.isZh ? '已生成脚本策略草稿。你可以复制代码，或跳转到脚本策略页面继续创建/运行。' : 'A script strategy draft is ready. Copy the code or open Script Strategy to continue creating/running it.',
          '',
          '```python',
          res.code,
          '```'
        ].join('\n')
        assistantMsg.meta = this.text.strategyGenerated
        assistantMsg.actions = [{
          key: 'open-script-strategy',
          group: 'strategy_workflow',
          icon: 'code',
          label: this.isZh ? '去脚本策略创建' : 'Open Script Strategy',
          path: '/strategy-script',
          storageKey: 'qd_copilot_script_strategy_code',
          storageValue: res.code,
          query: { aiDraft: '1', symbol: target.symbol, market: target.market }
        }]
        await this.persistCopilotMessage(assistantMsg, 'strategy_build')
        return
        this.$confirm({
          title: this.text.scriptStrategy,
          content: this.isZh ? '是否跳转到脚本策略页面继续创建？' : 'Open Script Strategy to continue creating it?',
          okText: this.text.openTargetPage,
          cancelText: this.text.cancel,
          onOk: () => this.$router.push({ path: '/strategy-script', query: { aiDraft: '1', symbol: target.symbol, market: target.market } })
        })
      } catch (e) {
        assistantMsg.content = `${this.text.chatUnavailable}\n\n${(e && e.message) || ''}`
      } finally {
        this.generatingStrategy = false
        this.scrollToBottom()
      }
    },
    async generateBotRecommendation (prompt, target) {
      this.generatingStrategy = true
      const assistantMsg = {
        localId: `local-${localId++}`,
        role: 'assistant',
        content: this.isZh ? '正在生成模板策略推荐...' : 'Generating template strategy recommendation...',
        meta: 'bot_recommend'
      }
      this.messages.push(assistantMsg)
      this.scrollToBottom()
      try {
        const agentPrompt = this.buildNativeStrategyGenerationPrompt('bot', prompt, target)
        const res = await aiGenerateStrategy({ prompt: agentPrompt, intent: 'bot_recommend' })
        const recommendation = res && res.bot_recommend
        if (!recommendation) throw new Error((res && res.msg) || 'AI bot recommendation failed')
        sessionStorage.setItem('qd_copilot_bot_recommend', JSON.stringify(recommendation))
        assistantMsg.content = [
          `## ${target.symbol} ${this.text.tradingBot}`,
          '',
          `- Bot type: ${recommendation.botType || '--'}`,
          `- Name: ${recommendation.botName || '--'}`,
          `- Reason: ${recommendation.reason || '--'}`,
          '',
          '```json',
          JSON.stringify(recommendation, null, 2),
          '```'
        ].join('\n')
        assistantMsg.meta = this.text.strategyGenerated
        assistantMsg.actions = [{
          key: 'open-trading-bot',
          group: 'strategy_workflow',
          icon: 'robot',
          label: this.isZh ? '去创建模板策略' : 'Open Template Strategy',
          path: '/trading-bot',
          storageKey: 'qd_copilot_bot_recommend',
          storageValue: recommendation,
          query: { aiPreset: '1' }
        }]
        await this.persistCopilotMessage(assistantMsg, 'bot_recommend')
        return
        this.$confirm({
          title: this.text.tradingBot,
          content: this.isZh ? '是否跳转到模板策略页面，用这份 AI 推荐继续创建？' : 'Open Template Strategy and continue with this AI recommendation?',
          okText: this.text.openTargetPage,
          cancelText: this.text.cancel,
          onOk: () => this.$router.push({ path: '/trading-bot', query: { aiPreset: '1' } })
        })
      } catch (e) {
        assistantMsg.content = `${this.text.chatUnavailable}\n\n${(e && e.message) || ''}`
      } finally {
        this.generatingStrategy = false
        this.scrollToBottom()
      }
    },
    openTaskModal (item) {
      this.taskTarget = item ? this.normalizeSymbolOption(item) : this.normalizeSymbolOption(this.context)
      this.taskForm = { interval_min: 240, notify_channels: [] }
      this.taskModalVisible = true
    },
    async saveMonitor () {
      const target = this.taskTarget || this.normalizeSymbolOption(this.context)
      if (!target || !target.symbol) return
      this.savingMonitor = true
      try {
        const interval = Number(this.taskForm.interval_min || 240)
        const res = await addMonitor({
          name: `AI-${target.symbol}-${interval}m`,
          position_ids: [],
          monitor_type: 'ai',
          config: {
            run_interval_minutes: interval,
            symbol: target.symbol,
            market: target.market,
            language: this.$store && this.$store.getters ? (this.$store.getters.lang || 'zh-CN') : (this.$i18n ? this.$i18n.locale : 'zh-CN')
          },
          notification_config: { channels: this.taskForm.notify_channels || [] },
          is_active: true
        })
        if (!res || res.code === 0) throw new Error((res && res.msg) || this.text.monitorCreated)
        this.$message.success(this.text.monitorCreated)
        this.taskModalVisible = false
        await this.loadMonitors()
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || 'Create monitor failed')
      } finally {
        this.savingMonitor = false
      }
    },
    async toggleMonitor (m) {
      try {
        await updateMonitor(m.id, { is_active: !m.is_active })
        this.$message.success(this.text.monitorUpdated)
        await this.loadMonitors()
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || 'Update monitor failed')
      }
    },
    async removeMonitor (m) {
      try {
        await deleteMonitor(m.id)
        this.$message.success(this.text.monitorDeleted)
        await this.loadMonitors()
      } catch (e) {
        this.$message.error((e && e.response && e.response.data && e.response.data.msg) || (e && e.message) || 'Delete monitor failed')
      }
    },
    handleFiles (e) {
      const files = Array.from(e.target.files || [])
      this.appendImageFiles(files)
      e.target.value = ''
    },
    appendImageFiles (files) {
      files.forEach(file => {
        if (!/^image\/(png|jpeg|webp)$/.test(file.type)) return
        const reader = new FileReader()
        reader.onload = () => {
          this.attachments.push({ name: file.name, mime_type: file.type, data_url: reader.result })
        }
        reader.readAsDataURL(file)
      })
    },
    handlePaste (event) {
      const items = Array.from((event.clipboardData && event.clipboardData.items) || [])
      const files = items
        .filter(item => item.kind === 'file' && /^image\/(png|jpeg|webp)$/.test(item.type))
        .map(item => item.getAsFile())
        .filter(Boolean)
      if (!files.length) return
      event.preventDefault()
      this.appendImageFiles(files)
      this.$message.success(this.isZh ? '图片已添加到本次对话' : 'Image added to this message')
    },
    removeAttachment (idx) {
      this.attachments.splice(idx, 1)
    },
    async sendMessage () {
      if (!this.canSend) return
      const content = this.draft.trim()
      const attachments = this.attachments.slice()
      const contextLock = this.draftContextLock ? { ...this.draftContextLock, locked: true } : null
      const signature = `${content}|${attachments.map(item => item.name || item.data_url || '').join(',')}`
      const now = Date.now()
      if (this.lastSendSignature === signature && now - this.lastSendAt < 1500) return
      this.lastSendSignature = signature
      this.lastSendAt = now
      this.sending = true
      const beforeSendCount = this.messages.length
      const createdAt = new Date().toISOString()
      this.messages.push({
        localId: `local-${localId++}`,
        role: 'user',
        content: content || (this.isZh ? '[已上传图片]' : '[image uploaded]'),
        attachments,
        created_at: createdAt
      })
      this.draft = ''
      this.attachments = []
      this.draftContextLock = null
      this.$nextTick(this.resizeComposer)
      this.scrollToBottom()
      if (this.pendingAgentTask && this.pendingAgentTask.type === 'monitor_setup' && await this.handleMonitorAgentMessage(content)) {
        const newMessages = this.messages.slice(beforeSendCount)
        for (const message of newMessages) {
          if (!message.id) await this.persistCopilotMessage(message, message.role === 'user' ? 'monitor_user' : 'monitor_agent')
        }
        this.sending = false
        this.scrollToBottom()
        return
      }
      if (this.pendingAgentTask) {
        this.pendingAgentTask.originalPrompt = content
      }
      if (await this.handleBackendAgentIntent(content, attachments, contextLock)) {
        this.sending = false
        this.scrollToBottom()
        return
      }
      await this.loadAgentPreflight()
      const blockers = this.agentPreflight && Array.isArray(this.agentPreflight.blockers) ? this.agentPreflight.blockers : []
      if (blockers.length) {
        const guide = this.buildPreflightGuide(this.pendingAgentTask)
        this.messages.push({
          localId: `local-${localId++}`,
          role: 'assistant',
          content: guide.content,
          actions: guide.actions,
          meta: guide.meta
        })
        await this.persistCopilotMessage(this.messages[this.messages.length - 1], 'preflight_guide')
        this.sending = false
        this.scrollToBottom()
        return
      }
      const assistantMsg = {
        localId: `local-${localId++}`,
        role: 'assistant',
        content: this.thinkingText,
        isThinking: true,
        meta: '',
        created_at: new Date().toISOString()
      }
      this.messages.push(assistantMsg)
      this.scrollToBottom()
      const resolvedSymbol = contextLock || await this.resolveMessageSymbol(content)
      if (resolvedSymbol) {
        const normalized = this.normalizeSymbolOption(resolvedSymbol)
        if (normalized) {
          this.context.market = normalized.market
          this.context.symbol = normalized.symbol
          this.selectedSymbolValue = this.symbolOptionValue(normalized)
          this.symbolOptions = [normalized].concat(this.symbolOptions || [])
        }
      }
      const chatContext = this.buildChatContext(content, resolvedSymbol)
      const preferJsonResponse = this.isMonitorIntent(content)
      if (!preferJsonResponse) {
        try {
          await this.sendMessageStream(content, attachments, assistantMsg, chatContext)
          this.sending = false
          this.scrollToBottom()
          return
        } catch (_) {
          assistantMsg.content = this.thinkingText
          assistantMsg.isThinking = true
        }
      }
      try {
        const res = await chatMessage({
          session_id: this.sessionId,
          message: content,
          attachments,
          context: chatContext,
          language: this.$i18n ? this.$i18n.locale : 'zh-CN'
        })
        if (res && res.code === 0) throw new Error(res.msg || this.text.chatUnavailable)
        const data = res.data || {}
        this.sessionId = data.session_id || this.sessionId
        const fallbackAssistant = this.replacePendingAssistant(assistantMsg, {
          localId: `local-${localId++}`,
          id: data.message_id || undefined,
          role: 'assistant',
          content: data.reply || this.text.chatUnavailable,
          isThinking: false,
          actions: data.actions || [],
          meta: data.intent ? `${data.intent} · ${data.confidence || 50}%` : ''
        })
        fallbackAssistant.created_at = fallbackAssistant.created_at || new Date().toISOString()
        this.appendMemoryActions(fallbackAssistant, data.memory_candidates)
        this.appendAgentNextActions(fallbackAssistant)
        this.loadSessions()
      } catch (e) {
        const guide = this.buildSetupGuide(e, chatContext)
        const setupMsg = this.replacePendingAssistant(assistantMsg, {
          localId: `local-${localId++}`,
          role: 'assistant',
          content: guide.content,
          isThinking: false,
          actions: guide.actions,
          meta: guide.meta
        })
        await this.persistCopilotMessage(setupMsg, 'setup_guide')
      } finally {
        this.sending = false
        this.scrollToBottom()
      }
    },
    normalizeSymbolOption (item) {
      if (!item) return null
      const market = item.market || item.market_type || item.category || this.context.market || 'Crypto'
      const symbol = String(item.symbol || item.code || item.ticker || '').trim()
      if (!symbol) return null
      return {
        market,
        symbol: symbol.toUpperCase(),
        name: item.name || item.display_name || item.label || ''
      }
    },
    parseSymbolValue (value) {
      const [market, ...rest] = String(value || '').split(':')
      return { market: market || this.context.market, symbol: rest.join(':') || '' }
    },
    symbolOptionValue (item) {
      return `${item.market}:${item.symbol}`
    },
    normalizePriceMap (raw) {
      if (!raw || typeof raw !== 'object') return {}
      const out = {}
      const list = Array.isArray(raw) ? raw : Object.keys(raw).map(key => raw[key])
      list.forEach(item => {
        if (item && item.market && item.symbol) out[`${item.market}:${item.symbol}`] = item
      })
      return out
    },
    eventTitle (event) {
      if (!event) return '--'
      if (this.isZh) return event.title_zh || event.name_zh || event.title || event.event || event.name || event.name_en || '--'
      return event.title_en || event.name_en || event.title || event.event || event.name || '--'
    },
    impactClass (event) {
      const raw = String((event && (event.impact || event.importance || event.importance_label)) || '').toLowerCase()
      if (raw.includes('high') || raw.includes('重要') || raw.includes('高')) return 'high'
      if (raw.includes('low') || raw.includes('低')) return 'low'
      return 'medium'
    },
    impactLabel (event) {
      const cls = this.impactClass(event)
      if (this.isZh) return cls === 'high' ? '高影响' : cls === 'low' ? '低影响' : '中影响'
      return cls === 'high' ? 'High' : cls === 'low' ? 'Low' : 'Medium'
    },
    formatEventTime (event) {
      const date = String((event && (event.date || event.datetime)) || '').slice(5, 10)
      const time = (event && event.time) || ''
      return `${date || '--'} ${time}`.trim()
    },
    eventKey (event) {
      return `${(event && (event.date || event.datetime)) || ''}-${(event && event.time) || ''}-${this.eventTitle(event)}`
    },
    formatMessageTime (msg) {
      const raw = msg && (msg.created_at || msg.createdAt || msg.timestamp || msg.time)
      if (!raw) return ''
      const date = new Date(raw)
      if (Number.isNaN(date.getTime())) return ''
      const pad = value => String(value).padStart(2, '0')
      const now = new Date()
      const sameDay = date.getFullYear() === now.getFullYear() &&
        date.getMonth() === now.getMonth() &&
        date.getDate() === now.getDate()
      const time = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
      return sameDay ? time : `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${time.slice(0, 5)}`
    },
    normalizeMessages (list = []) {
      const seenIds = new Set()
      const out = []
      ;(Array.isArray(list) ? list : []).forEach(raw => {
        if (!raw) return
        const msg = { ...raw }
        if (msg.id) {
          const idKey = String(msg.id)
          if (seenIds.has(idKey)) return
          seenIds.add(idKey)
        }
        const prev = out[out.length - 1]
        if (prev && prev.role === msg.role && String(prev.content || '') === String(msg.content || '')) {
          const prevTs = Date.parse(prev.created_at || prev.createdAt || '')
          const ts = Date.parse(msg.created_at || msg.createdAt || '')
          if (!prevTs || !ts || Math.abs(ts - prevTs) < 10000) return
        }
        if (msg.report && (!Array.isArray(msg.actions) || !msg.actions.length)) {
          msg.actions = this.reportActions(msg)
        }
        out.push(msg)
      })
      return out
    },
    macroContextForMessage (message = '') {
      const lower = String(message || '').toLowerCase()
      const keywords = ['非农', 'nfp', 'cpi', 'fomc', 'fed', '利率', '就业', '失业', 'pce', 'gdp', '通胀', 'inflation', 'payroll']
      const enabled = keywords.some(key => lower.includes(String(key).toLowerCase()))
      if (!enabled) return { enabled: false, events: [] }
      const events = (this.calendarEvents || []).slice(0, 30).map(event => ({
        title: this.eventTitle(event),
        date: event.date || event.datetime || '',
        time: event.time || '',
        impact: event.impact || event.importance || event.importance_label || '',
        country: event.country || event.region || event.currency || '',
        actual: event.actual,
        forecast: event.forecast,
        previous: event.previous
      }))
      return { enabled, events }
    },
    async sendMessageStream (content, attachments, assistantMsg, chatContext = null) {
      if (!window.fetch || !window.ReadableStream) throw new Error('Streaming is not supported')
      const language = this.$i18n ? this.$i18n.locale : 'zh-CN'
      const headers = {
        'Content-Type': 'application/json',
        'Accept-Language': language,
        'X-App-Lang': language,
        'Cache-Control': 'no-cache'
      }
      const token = this.getAccessToken()
      if (token) {
        headers.Authorization = `Bearer ${token}`
        headers[ACCESS_TOKEN] = token
        headers.token = token
      }
      const response = await fetch('/api/ai/chat/message/stream', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          session_id: this.sessionId,
          message: content,
          attachments,
          context: chatContext || this.buildChatContext(content),
          language
        })
      })
      if (!response.ok || !response.body) throw new Error(`Stream API ${response.status}`)
      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split(/\r?\n\r?\n/)
        buffer = parts.pop() || ''
        parts.forEach(part => this.handleStreamEvent(part, assistantMsg))
        this.scrollToBottom()
      }
      if (buffer.trim()) this.handleStreamEvent(buffer, assistantMsg)
      if (assistantMsg.isThinking) {
        assistantMsg.content = ''
        assistantMsg.isThinking = false
      }
      if (!assistantMsg.content) throw new Error('Empty stream response')
      this.loadSessions()
    },
    handleStreamEvent (rawEvent, assistantMsg) {
      const lines = String(rawEvent || '').split(/\r?\n/)
      const eventName = (lines.find(line => line.startsWith('event:')) || '').replace(/^event:\s*/, '').trim()
      const data = lines
        .filter(line => line.startsWith('data:'))
        .map(line => line.replace(/^data:\s*/, ''))
        .join('\n')
      if (!data) return
      const payload = JSON.parse(data)
      if (eventName === 'meta') {
        this.sessionId = payload.session_id || this.sessionId
        assistantMsg.meta = payload.intent || ''
      } else if (eventName === 'delta') {
        if (payload.text) this.clearThinkingMessage(assistantMsg)
        assistantMsg.content += payload.text || ''
      } else if (eventName === 'done') {
        this.sessionId = payload.session_id || this.sessionId
        if (payload.message_id) this.$set ? this.$set(assistantMsg, 'id', payload.message_id) : (assistantMsg.id = payload.message_id)
        assistantMsg.created_at = assistantMsg.created_at || new Date().toISOString()
        assistantMsg.meta = payload.intent ? `${payload.intent} - ${payload.confidence || 50}%` : assistantMsg.meta
        this.appendMemoryActions(assistantMsg, payload.memory_candidates)
        this.appendAgentNextActions(assistantMsg)
      } else if (eventName === 'error') {
        throw new Error(payload.msg || this.text.chatUnavailable)
      }
    },
    getAccessToken () {
      return storage.get(ACCESS_TOKEN) || storage.get('Authorization') || storage.get('token') || ''
    },
    escapeHtml (value) {
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
    },
    renderInlineMarkdown (value) {
      return this.escapeHtml(value)
        .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    },
    renderMarkdown (text) {
      const source = String(text || '').replace(/\r\n/g, '\n')
      const blocks = []
      const withTokens = source.replace(/```([\w+-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
        const idx = blocks.length
        const label = lang || 'text'
        blocks.push(
          `<div class="qd-code-block">` +
          `<div class="qd-code-head"><span>${this.escapeHtml(label)}</span><button type="button" class="qd-copy-code" data-code="${encodeURIComponent(code)}">Copy</button></div>` +
          `<pre><code class="language-${this.escapeHtml(label)}">${this.escapeHtml(code)}</code></pre>` +
          `</div>`
        )
        return `\n@@CODE_BLOCK_${idx}@@\n`
      })
      const lines = withTokens.split('\n')
      const out = []
      let listType = ''
      let paragraph = []
      const closeList = () => {
        if (listType) {
          out.push(`</${listType}>`)
          listType = ''
        }
      }
      const closeParagraph = () => {
        if (paragraph.length) {
          out.push(`<p>${paragraph.map(item => this.renderInlineMarkdown(item)).join('<br>')}</p>`)
          paragraph = []
        }
      }
      const closeBlocks = () => {
        closeParagraph()
        closeList()
      }
      const renderTable = (rows) => {
        const cells = rows
          .map(row => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim()))
          .filter(row => row.length > 1)
        if (cells.length < 2) return ''
        const header = cells[0]
        const body = cells.slice(2)
        return [
          '<div class="qd-md-table-wrap"><table class="qd-md-table">',
          '<thead><tr>',
          header.map(cell => `<th>${this.renderInlineMarkdown(cell)}</th>`).join(''),
          '</tr></thead>',
          '<tbody>',
          body.map(row => `<tr>${row.map(cell => `<td>${this.renderInlineMarkdown(cell)}</td>`).join('')}</tr>`).join(''),
          '</tbody></table></div>'
        ].join('')
      }
      for (let index = 0; index < lines.length; index++) {
        const line = lines[index]
        const trimmed = line.trim()
        const token = line.match(/^@@CODE_BLOCK_(\d+)@@$/)
        if (token) {
          closeBlocks()
          out.push(blocks[Number(token[1])] || '')
          continue
        }
        if (!trimmed) {
          closeBlocks()
          continue
        }
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
          closeBlocks()
          out.push('<hr>')
          continue
        }
        const nextLine = lines[index + 1] || ''
        if (trimmed.includes('|') && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(nextLine)) {
          closeBlocks()
          const tableRows = [line, nextLine]
          index += 2
          while (index < lines.length && lines[index].trim().includes('|')) {
            tableRows.push(lines[index])
            index++
          }
          index--
          out.push(renderTable(tableRows))
          continue
        }
        const heading = trimmed.match(/^(#{1,4})\s+(.+)$/)
        if (heading) {
          closeBlocks()
          const level = Math.min(heading[1].length + 2, 5)
          out.push(`<h${level}>${this.renderInlineMarkdown(heading[2])}</h${level}>`)
          continue
        }
        const plainHeading = trimmed.match(/^(\d+)[).、）]\s*(.{2,80})$/)
        if (plainHeading) {
          closeBlocks()
          out.push(`<h4>${this.renderInlineMarkdown(`${plainHeading[1]}. ${plainHeading[2]}`)}</h4>`)
          continue
        }
        const quote = trimmed.match(/^>\s+(.+)$/)
        if (quote) {
          closeBlocks()
          out.push(`<blockquote>${this.renderInlineMarkdown(quote[1])}</blockquote>`)
          continue
        }
        const ordered = trimmed.match(/^\d+[.)、）]\s+(.+)$/)
        const unordered = trimmed.match(/^[-*+]\s+(.+)$/)
        if (ordered || unordered) {
          closeParagraph()
          const target = ordered ? 'ol' : 'ul'
          if (listType !== target) {
            closeList()
            out.push(`<${target}>`)
            listType = target
          }
          out.push(`<li>${this.renderInlineMarkdown((ordered || unordered)[1])}</li>`)
          continue
        }
        closeList()
        paragraph.push(line)
      }
      closeParagraph()
      closeList()
      return out.join('')
    },
    async handleMessageContentClick (event) {
      const btn = event.target && event.target.closest ? event.target.closest('.qd-copy-code') : null
      if (!btn) return
      const code = decodeURIComponent(btn.getAttribute('data-code') || '')
      try {
        await navigator.clipboard.writeText(code)
      } catch (_) {
        const textarea = document.createElement('textarea')
        textarea.value = code
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      this.$message.success(this.isZh ? '代码已复制' : 'Code copied')
    },
    setupAction (key) {
      const map = {
        ai: {
          key: 'settings-ai',
          icon: 'setting',
          label: this.i18nText('aiCopilot.setup.action.ai', this.isZh ? '配置 AI/LLM' : 'Configure AI/LLM'),
          path: '/settings',
          query: { section: 'ai' }
        },
        data: {
          key: 'settings-data',
          icon: 'database',
          label: this.i18nText('aiCopilot.setup.action.data', this.isZh ? '配置数据源' : 'Configure data sources'),
          path: '/settings',
          query: { section: 'data_source' }
        },
        broker: {
          key: 'broker-accounts',
          icon: 'bank',
          label: this.i18nText('aiCopilot.setup.action.broker', this.isZh ? '配置券商账户' : 'Configure broker accounts'),
          path: '/broker-accounts'
        },
        billing: {
          key: 'billing',
          icon: 'wallet',
          label: this.i18nText('aiCopilot.setup.action.billing', this.isZh ? '去充值' : 'Top up'),
          path: '/billing'
        },
        credits: {
          key: 'profile-credits',
          icon: 'profile',
          label: this.i18nText('aiCopilot.setup.action.credits', this.isZh ? '查看消费记录' : 'View credit records'),
          path: '/profile',
          query: { tab: 'credits' }
        },
        login: {
          key: 'login',
          icon: 'login',
          label: this.i18nText('aiCopilot.setup.action.login', this.isZh ? '重新登录' : 'Sign in again'),
          path: '/user/login'
        }
      }
      return map[key]
    },
    classifySetupIssue (raw) {
      const text = String(raw || '')
      const lower = text.toLowerCase()
      const includesAny = patterns => patterns.some(pattern => pattern.test ? pattern.test(text) : lower.includes(pattern))
      if (includesAny([
        /local-only|not implemented/i,
        /llm|large language model|provider|model provider|api key|apikey|base url|openrouter|openai|anthropic|deepseek|atlascloud/i,
        /未配置|大模型|模型供应商|模型提供商|密钥|接口密钥|api\s*key/i
      ])) return 'llm'
      if (includesAny([
        /insufficient|credit|credits|billing|quota|payment|vip/i,
        /积分|余额不足|额度|充值|会员|扣费/i
      ])) return 'billing'
      if (includesAny([
        /broker|broker account|exchange account|credential|api secret|trade account/i,
        /券商|交易所账户|经纪商|账户未配置|交易账户|实盘账户/i
      ])) return 'broker'
      if (includesAny([
        /data source|market data|quote|quotes|price feed|symbol not found|no data|provider unavailable|akshare|tushare|yfinance|ccxt/i,
        /数据源|行情源|行情接口|行情数据|报价|价格数据|标的不存在|没有数据/i
      ])) return 'data'
      if (includesAny([
        /401|403|unauthorized|forbidden|permission|token|login/i,
        /未登录|登录|权限|无权限|令牌/i
      ])) return 'auth'
      if (includesAny([
        /network|timeout|failed to fetch|502|503|504|gateway|connection|econn/i,
        /网络|超时|连接失败|服务不可用|网关/i
      ])) return 'network'
      return 'unknown'
    },
    buildSetupGuide (error, context = {}) {
      const raw = (error && error.response && error.response.data && error.response.data.msg) || (error && error.message) || ''
      const type = this.classifySetupIssue(raw)
      const symbol = context && context.symbol ? `${context.market || ''}:${context.symbol}`.replace(/^:/, '') : ''
      const baseActions = []
      const zh = this.isZh
      const rawLine = raw ? `\n\n> ${raw}` : ''
      if (type === 'llm') {
        return {
          meta: zh ? '部署检查：AI/LLM' : 'Setup check: AI/LLM',
          content: zh
            ? [
                '### 需要先配置大模型',
                '',
                '我已经收到你的问题，但当前 AI 对话没有可用的大模型配置，所以无法继续生成有效回答。',
                '',
                '**建议处理：**',
                '- 进入「系统设置 → AI/LLM配置」选择模型供应商。',
                '- 填写对应供应商的 API Key、模型名称和 Base URL。',
                '- 保存后如果后端读取环境配置，请重构并重启后端 Docker。',
                '',
                '配置完成后，你可以直接回到这里继续问，不需要手动选择数据源。'
              ].join('\n') + rawLine
            : [
                '### Configure an LLM first',
                '',
                'I received your question, but no usable LLM provider is available yet.',
                '',
                '**Next steps:**',
                '- Open Admin → AI/LLM settings.',
                '- Fill the provider API key, model, and Base URL.',
                '- Save settings and restart the backend Docker service if the backend reads environment config.',
                '',
                'After that, come back here and ask naturally.'
              ].join('\n') + rawLine,
          actions: [this.setupAction('ai')].filter(Boolean)
        }
      }
      if (type === 'data') {
        return {
          meta: zh ? '部署检查：数据源' : 'Setup check: data source',
          content: zh
            ? [
                '### 行情数据源可能还没配置好',
                '',
                symbol
                  ? `我识别到你想分析 **${symbol}**，但系统没有拿到可用行情/报价数据。`
                  : '我尝试从你的问题里识别标的，但系统没有拿到可用行情/报价数据。',
                '',
                '**建议处理：**',
                '- 进入「系统设置 → 数据源」检查行情源配置。',
                '- 加密货币通常需要交易所/CCXT 或行情接口可用。',
                '- A股/港股/美股需要对应数据源配置和网络访问正常。',
                '- 如果只是临时没有实时价格，我仍可以基于你上传的K线图或手动给出的价格区间继续分析。'
              ].join('\n') + rawLine
            : [
                '### Market data source may not be configured',
                '',
                symbol
                  ? `I recognized **${symbol}**, but the system could not fetch usable quotes or market data.`
                  : 'I tried to infer the symbol, but no usable quotes or market data were available.',
                '',
                '**Next steps:**',
                '- Open Admin → Data source settings.',
                '- Check exchange/CCXT or quote-provider configuration.',
                '- For stocks, confirm the corresponding market data provider and network access.',
                '- You can still upload a chart or provide price levels and I can continue from that.'
              ].join('\n') + rawLine,
          actions: [this.setupAction('data')].filter(Boolean)
        }
      }
      if (type === 'broker') {
        return {
          meta: zh ? '部署检查：券商账户' : 'Setup check: broker account',
          content: zh
            ? [
                '### 交易账户还没有配置',
                '',
                '这类操作需要可用的券商/交易所账户。当前系统没有检测到可用账户或凭证。',
                '',
                '**建议处理：**',
                '- 进入「券商账户」添加交易所或券商连接。',
                '- 先使用只读/模拟盘确认行情、持仓和订单接口正常。',
                '- 确认风险参数后再开启自动交易或实盘动作。'
              ].join('\n') + rawLine
            : [
                '### Broker account is not configured',
                '',
                'This action needs a connected broker or exchange account.',
                '',
                '**Next steps:**',
                '- Open Broker Accounts and add a broker/exchange connection.',
                '- Test read-only or paper trading first.',
                '- Confirm risk parameters before enabling live automation.'
              ].join('\n') + rawLine,
          actions: [this.setupAction('broker')].filter(Boolean)
        }
      }
      if (type === 'billing') {
        return {
          meta: zh ? '部署检查：积分/额度' : 'Setup check: credits',
          content: zh
            ? [
                '### 当前积分或额度不足',
                '',
                'AI 对话、图片分析、回测或监控可能会消耗积分。当前请求没有足够额度继续执行。',
                '',
                '**建议处理：**',
                '- 前往充值页面补充积分或开通会员。',
                '- 到个人中心查看消费记录，确认是哪项功能产生了消耗。'
              ].join('\n') + rawLine
            : [
                '### Not enough credits or quota',
                '',
                'AI chat, image analysis, backtests, or monitors may consume credits.',
                '',
                '**Next steps:**',
                '- Top up credits or purchase a membership.',
                '- Review credit records in your profile.'
              ].join('\n') + rawLine,
          actions: [this.setupAction('billing'), this.setupAction('credits')].filter(Boolean)
        }
      }
      if (type === 'auth') {
        return {
          meta: zh ? '部署检查：登录/权限' : 'Setup check: auth',
          content: zh
            ? '### 登录状态或权限异常\n\n当前请求没有通过认证或权限检查。请重新登录，或确认当前账号有访问 AI 分析/系统设置的权限。' + rawLine
            : '### Sign-in or permission issue\n\nThis request did not pass authentication or permission checks. Please sign in again or confirm your account has access to AI analysis/settings.' + rawLine,
          actions: [this.setupAction('login')].filter(Boolean)
        }
      }
      if (type === 'network') {
        baseActions.push(this.setupAction('ai'), this.setupAction('data'))
        return {
          meta: zh ? '部署检查：服务连接' : 'Setup check: service connection',
          content: zh
            ? [
                '### 后端服务或外部接口暂时不可用',
                '',
                '这通常不是你的提问问题，而是服务连接、Docker 后端、外部模型接口或行情接口暂时不可达。',
                '',
                '**建议处理：**',
                '- 确认后端 Docker 服务正在运行。',
                '- 检查模型供应商和行情源网络是否可访问。',
                '- 如果刚修改配置，请保存后重启对应后端服务。'
              ].join('\n') + rawLine
            : [
                '### Backend service or external provider is unavailable',
                '',
                'This is usually a service connectivity issue rather than a prompt issue.',
                '',
                '**Next steps:**',
                '- Confirm the backend Docker service is running.',
                '- Check LLM provider and market data network access.',
                '- Restart backend services after configuration changes.'
              ].join('\n') + rawLine,
          actions: baseActions.filter(Boolean)
        }
      }
      return {
        meta: zh ? '部署检查' : 'Setup check',
        content: `${this.text.chatUnavailable}${rawLine}\n\n${zh ? '你也可以先检查：系统设置里的 AI/LLM、数据源配置，以及券商账户是否已连接。' : 'You can also check AI/LLM settings, data source settings, and broker account connections.'}`,
        actions: [this.setupAction('ai'), this.setupAction('data'), this.setupAction('broker')].filter(Boolean)
      }
    },
    scrollToBottom () {
      this.$nextTick(() => {
        const el = this.$refs.messages
        if (el) el.scrollTop = el.scrollHeight
      })
    },
    watchKey (item) {
      return `${item.market}:${item.symbol}`
    },
    priceFor (item) {
      return this.watchlistPrices[this.watchKey(item)] || null
    },
    priceChangePercent (price) {
      if (!price) return null
      const candidates = [price.changePercent, price.change_percent, price.changePct, price.change_pct, price.percent]
      for (const value of candidates) {
        const n = Number(value)
        if (Number.isFinite(n)) return n
      }
      return null
    },
    watchChangeClass (item) {
      const pct = this.priceChangePercent(this.priceFor(item))
      if (pct === null) return ''
      return pct >= 0 ? 'up' : 'down'
    },
    formatPriceValue (value) {
      const n = Number(value)
      if (!Number.isFinite(n) || n <= 0) return '--'
      if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
      if (n >= 1) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })
      return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })
    },
    formatChangePercent (price) {
      const pct = this.priceChangePercent(price)
      if (pct === null) return '--'
      return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
    },
    i18nText (key, fallback, values) {
      const translated = this.$t ? this.$t(key, values) : key
      if (translated && translated !== key) return translated
      return Object.entries(values || {}).reduce((text, [name, value]) => {
        return text.replace(new RegExp(`\\{${name}\\}`, 'g'), value)
      }, fallback)
    },
    marketLabel (market) {
      const key = `dashboard.analysis.market.${market}`
      const translated = this.$t ? this.$t(key) : key
      if (translated && translated !== key) return translated
      const found = this.markets.find(m => m.value === market)
      return found ? found.label : (market || '--')
    },
    marketPillClass (market) {
      return `market-${String(market || 'default').toLowerCase()}`
    },
    monitorSymbol (m) {
      const cfg = m.config || {}
      return cfg.symbol || m.symbol || m.name || '--'
    },
    intervalText (m) {
      const minutes = Number((m.config && m.config.run_interval_minutes) || m.interval_min || 0)
      if (!minutes) return '--'
      if (minutes >= 1440) return `${Math.round(minutes / 1440)}d`
      if (minutes >= 60) return `${Math.round(minutes / 60)}h`
      return `${minutes}m`
    },
    formatIntervalText (value) {
      const minutes = Number(value || 0)
      if (!minutes) return this.isZh ? '未设置' : 'Not set'
      if (minutes >= 1440 && minutes % 1440 === 0) {
        const days = Math.round(minutes / 1440)
        return this.isZh ? `每${days}天` : `${days}d`
      }
      if (minutes >= 60 && minutes % 60 === 0) {
        const hours = Math.round(minutes / 60)
        return this.isZh ? `每${hours}小时` : `${hours}h`
      }
      return this.isZh ? `每${minutes}分钟` : `${minutes}m`
    },
    formatNum (num) {
      const n = Number(num)
      if (!Number.isFinite(n)) return '--'
      return n.toFixed(2)
    }
  }
}
</script>

<style scoped lang="less">
.copilot-workbench {
  --qd-bg: #eef3f8;
  --qd-panel: #ffffff;
  --qd-panel-soft: #f7fafd;
  --qd-panel-strong: #f1f6fb;
  --qd-border: #dce6f1;
  --qd-border-soft: #e8eff7;
  --qd-text: #12243d;
  --qd-text-muted: #6b7f99;
  --qd-text-subtle: #92a2b6;
  --qd-accent: var(--primary-color, #1677ff);
  --qd-accent-soft: color-mix(in srgb, var(--qd-accent) 10%, #ffffff);
  --qd-accent-weak: color-mix(in srgb, var(--qd-accent) 8%, transparent);
  --qd-accent-border: color-mix(in srgb, var(--qd-accent) 42%, transparent);
  --qd-accent-ring: color-mix(in srgb, var(--qd-accent) 12%, transparent);
  --qd-green: #0aa375;
  --qd-red: #e54b4b;
  --qd-shadow: 0 12px 34px rgba(20, 43, 72, 0.08);

  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(560px, 1fr) minmax(270px, 320px);
  gap: 10px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.7), rgba(238, 243, 248, 0.88)),
    var(--qd-bg);
  color: var(--qd-text);
}

.left-rail,
.right-rail,
.chat-panel {
  min-width: 0;
  min-height: 0;
}

.left-rail,
.right-rail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.rail-panel,
.chat-panel {
  background: color-mix(in srgb, var(--qd-panel) 82%, transparent);
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  box-shadow: var(--qd-shadow);
  backdrop-filter: blur(18px);
}

.rail-panel {
  padding: 12px;
  overflow: hidden;
}

.sessions-panel {
  flex: 1 1 330px;
  min-height: 280px;
  display: flex;
  flex-direction: column;
}

.calendar-panel {
  flex: 0 1 42%;
  min-height: 220px;
}

.watch-panel {
  flex: 0 0 58%;
  min-height: 0;
}

.monitor-panel {
  flex: 1 1 270px;
  min-height: 240px;
}

.panel-head {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 30px;
  margin-bottom: 10px;
  color: var(--qd-text);
  font-size: 13px;
  font-weight: 700;
}

.panel-head .anticon {
  color: var(--qd-accent);
}

.panel-head ::v-deep .ant-btn-link {
  height: 28px;
  padding: 0 4px;
  color: var(--qd-accent);
  font-weight: 600;
}

.segmented {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  padding: 3px;
  margin-bottom: 10px;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel-soft);
}

.segmented button {
  min-width: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--qd-text-muted);
  font-size: 12px;
  line-height: 26px;
  cursor: pointer;
  transition: background 0.18s, color 0.18s, box-shadow 0.18s;
}

.segmented button.active {
  background: var(--qd-panel);
  color: var(--qd-accent);
  font-weight: 700;
  box-shadow: 0 1px 5px rgba(20, 43, 72, 0.08);
}

.session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 3px;
  scrollbar-width: thin;
}

.session-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 5px;
  margin-bottom: 6px;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel-soft);
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s, transform 0.18s;
}

.session-row:hover {
  border-color: var(--qd-accent-border);
  background: var(--qd-panel);
  box-shadow: 0 6px 18px var(--qd-accent-weak);
  transform: translateY(-1px);
}

.session-row.active {
  border-color: color-mix(in srgb, var(--qd-accent) 58%, transparent);
  background: var(--qd-accent-soft);
}

.session-delete {
  width: 24px;
  height: 28px;
  margin-right: 4px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #7590ae;
  cursor: pointer;
}

.session-delete:hover {
  color: var(--qd-red);
  background: rgba(229, 75, 75, 0.1);
}

.session-card,
.calendar-card {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s, transform 0.18s;
}

.calendar-card:hover {
  border-color: var(--qd-accent-border);
  background: var(--qd-panel);
  box-shadow: 0 6px 18px var(--qd-accent-weak);
  transform: translateY(-1px);
}

.session-card {
  display: block;
  padding: 9px 10px;
}

.session-card strong,
.watch-main strong,
.monitor-card strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: var(--qd-text);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-card span,
.watch-main em,
.monitor-card span {
  display: block;
  min-width: 0;
  margin-top: 2px;
  overflow: hidden;
  color: var(--qd-text-subtle);
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.calendar-list,
.watch-list,
.monitor-list {
  display: grid;
  gap: 7px;
  overflow-y: auto;
  max-height: calc(100% - 72px);
  padding-right: 3px;
  scrollbar-width: thin;
}

.session-list + .empty-mini,
.sessions-panel > .empty-mini {
  flex: 1;
}

.calendar-card {
  border: 1px solid var(--qd-border-soft);
  background: var(--qd-panel-soft);
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 8px 9px;
}

.calendar-card strong {
  min-width: 0;
  overflow: hidden;
  color: var(--qd-text);
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-time {
  color: var(--qd-text-subtle);
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 11px;
}

.impact-pill {
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
  font-style: normal;
  font-weight: 700;
  background: #fff4d6;
  color: #9a6200;
  white-space: nowrap;
}

.impact-pill.high {
  background: #ffe7e5;
  color: #b42318;
}

.impact-pill.low {
  background: #e9fbdc;
  color: #237804;
}

.empty-mini,
.error-note {
  min-height: 56px;
  display: grid;
  place-items: center;
  padding: 12px;
  border: 1px dashed var(--qd-border);
  border-radius: 8px;
  color: var(--qd-text-subtle);
  background: var(--qd-panel-soft);
  text-align: center;
}

.error-note {
  color: #d46b08;
  background: #fff8e8;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-hero {
  padding: 9px 16px;
  border-bottom: 1px solid var(--qd-border-soft);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--qd-accent) 7%, transparent), rgba(255, 255, 255, 0.08)),
    color-mix(in srgb, var(--qd-panel) 76%, transparent);
}

.hero-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 390px);
  gap: 14px;
  align-items: center;
}

.hero-copy {
  min-width: 0;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  min-height: 17px;
  margin-bottom: 3px;
  padding: 1px 7px;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 28%, transparent);
  border-radius: 999px;
  background: var(--qd-accent-soft);
  color: var(--qd-accent);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0;
}

.chat-hero h2 {
  margin: 0 0 2px;
  color: var(--qd-text);
  font-size: 18px;
  font-weight: 800;
  line-height: 1.25;
}

.chat-hero p {
  max-width: 680px;
  margin: 0;
  color: var(--qd-text-muted);
  font-size: 12px;
  line-height: 1.35;
}

.context-bar {
  display: grid;
  grid-template-columns: 1fr;
  gap: 5px;
  align-items: stretch;
  min-width: 0;
  margin-top: 0;
}

.context-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--qd-text-muted);
  font-size: 11px;
}

.context-status .anticon {
  color: var(--qd-accent);
}

.context-status span {
  flex: 0 0 auto;
  font-weight: 700;
}

.context-status strong {
  min-width: 0;
  overflow: hidden;
  color: var(--qd-text-muted);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-symbol-picker {
  min-width: 0;
}

.composer-actions ::v-deep .ant-btn,
.add-watch ::v-deep .ant-btn {
  border-radius: 6px;
  font-weight: 700;
}

.symbol-picker label {
  display: block;
  margin-bottom: 5px;
  color: var(--qd-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.symbol-picker ::v-deep .ant-select {
  width: 100%;
}

.hero-symbol-picker ::v-deep .ant-select-selection {
  height: 32px;
}

.hero-symbol-picker ::v-deep .ant-select-selection__rendered {
  line-height: 30px;
}

.symbol-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.symbol-option span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: var(--qd-text-subtle);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.symbol-market-pill {
  flex: 0 0 auto;
  min-width: 56px;
  padding: 2px 7px;
  border: 1px solid var(--qd-border-soft);
  border-radius: 5px;
  background: var(--qd-panel-strong);
  color: var(--qd-text-muted);
  font-size: 10px;
  font-style: normal;
  font-weight: 800;
  line-height: 1.25;
  text-align: center;
}

.market-crypto {
  border-color: rgba(20, 184, 166, 0.34);
  background: rgba(20, 184, 166, 0.13);
  color: #14b8a6;
}

.market-usstock {
  border-color: rgba(59, 130, 246, 0.34);
  background: rgba(59, 130, 246, 0.13);
  color: #3b82f6;
}

.market-hkstock {
  border-color: rgba(139, 92, 246, 0.34);
  background: rgba(139, 92, 246, 0.13);
  color: #8b5cf6;
}

.market-cnstock {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.market-forex {
  border-color: rgba(34, 197, 94, 0.34);
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.market-futures {
  border-color: rgba(245, 158, 11, 0.36);
  background: rgba(245, 158, 11, 0.13);
  color: #d97706;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px 20px;
  background:
    radial-gradient(circle at 50% 8%, color-mix(in srgb, var(--qd-accent) 8%, transparent), transparent 34%),
    linear-gradient(180deg, rgba(247, 250, 253, 0.86) 0%, rgba(255, 255, 255, 0.94) 54%, rgba(247, 250, 253, 0.9) 100%);
}

.welcome {
  max-width: 880px;
  margin: 38px auto 0;
  text-align: center;
  color: var(--qd-text-muted);
}

.welcome > .anticon {
  display: inline-grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 24%, transparent);
  border-radius: 8px;
  background: var(--qd-accent-soft);
  color: var(--qd-accent);
  font-size: 22px;
}

.welcome h3 {
  margin: 12px 0 4px;
  color: var(--qd-text);
  font-size: 21px;
  font-weight: 800;
}

.welcome-prompts {
  display: grid;
  grid-template-columns: repeat(4, minmax(138px, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.welcome-prompts button {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-height: 76px;
  padding: 11px 12px;
  border: 1px solid var(--qd-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--qd-panel) 88%, transparent);
  color: var(--qd-text);
  cursor: pointer;
  text-align: left;
  backdrop-filter: blur(14px);
  transition: border-color 0.18s, color 0.18s, background 0.18s, transform 0.18s, box-shadow 0.18s;
}

.welcome-prompts button:hover {
  border-color: var(--qd-accent-border);
  background: var(--qd-accent-soft);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.welcome-prompts button:hover .task-icon {
  border-color: var(--qd-accent-border);
  color: #fff;
  background: var(--qd-accent);
}

.task-icon {
  display: inline-grid;
  flex: 0 0 30px;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 22%, transparent);
  border-radius: 7px;
  background: var(--qd-accent-soft);
  color: var(--qd-accent);
  font-size: 15px;
  transition: border-color 0.18s, color 0.18s, background 0.18s;
}

.task-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.task-copy strong {
  color: var(--qd-text);
  font-size: 13px;
  font-weight: 800;
  line-height: 1.2;
}

.task-copy em {
  color: var(--qd-text-muted);
  font-size: 11px;
  font-style: normal;
  line-height: 1.45;
}

.message {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 20%, transparent);
  border-radius: 8px;
  background: var(--qd-accent-soft);
  color: var(--qd-accent);
  flex: 0 0 34px;
}

.message.user .avatar {
  border-color: rgba(10, 163, 117, 0.16);
  background: rgba(10, 163, 117, 0.1);
  color: var(--qd-green);
}

.bubble {
  max-width: 820px;
  width: fit-content;
  padding: 12px 14px;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel);
  color: var(--qd-text);
  line-height: 1.72;
  box-shadow: 0 4px 16px rgba(20, 43, 72, 0.045);
}

.message.report-message.assistant .bubble {
  width: 100%;
  max-width: 920px;
  padding: 0;
  overflow: hidden;
  background: transparent;
  border: 0;
  box-shadow: none;
}

.copilot-report-card {
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel);
}

.message.user .bubble {
  background: var(--qd-accent-soft);
}

.message.thinking-message .bubble {
  border-style: dashed;
  color: var(--qd-text-muted);
}

.message.thinking-message .message-content {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 800;
}

.message.thinking-message .message-content::before {
  content: '';
  width: 14px;
  height: 14px;
  border: 2px solid color-mix(in srgb, var(--qd-accent) 18%, transparent);
  border-top-color: var(--qd-accent);
  border-radius: 50%;
  animation: qd-copilot-spin 0.8s linear infinite;
}

@keyframes qd-copilot-spin {
  to {
    transform: rotate(360deg);
  }
}

.message-content ::v-deep h3,
.message-content ::v-deep h4 {
  margin: 14px 0 8px;
  color: var(--qd-text);
  line-height: 1.45;
}

.message-content ::v-deep h5 {
  margin: 10px 0 6px;
  color: var(--qd-text);
  font-size: 14px;
  line-height: 1.45;
}

.message-content ::v-deep p {
  margin: 0 0 10px;
  line-height: 1.78;
}

.message-content ::v-deep p:last-child {
  margin-bottom: 0;
}

.message-content ::v-deep ul,
.message-content ::v-deep ol {
  margin: 8px 0 12px;
  padding-left: 22px;
}

.message-content ::v-deep ul {
  list-style: disc;
}

.message-content ::v-deep ol {
  list-style: decimal;
}

.message-content ::v-deep li {
  margin: 5px 0;
  padding-left: 2px;
  line-height: 1.68;
}

.message-content ::v-deep hr {
  height: 1px;
  margin: 14px 0;
  border: 0;
  background: var(--qd-border-soft);
}

.message-content ::v-deep blockquote {
  margin: 10px 0;
  padding: 9px 11px;
  border-left: 3px solid var(--qd-accent-border);
  border-radius: 0 6px 6px 0;
  background: var(--qd-panel-soft);
  color: var(--qd-text-muted);
}

.message-content ::v-deep .qd-md-table-wrap {
  max-width: 100%;
  margin: 10px 0 14px;
  overflow-x: auto;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
}

.message-content ::v-deep .qd-md-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.message-content ::v-deep .qd-md-table th,
.message-content ::v-deep .qd-md-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--qd-border-soft);
  color: var(--qd-text);
  text-align: left;
  vertical-align: top;
}

.message-content ::v-deep .qd-md-table th {
  background: var(--qd-panel-strong);
  color: var(--qd-text-muted);
  font-weight: 800;
}

.message-content ::v-deep .qd-md-table tr:last-child td {
  border-bottom: 0;
}

.message-content ::v-deep a {
  color: var(--qd-accent);
  text-decoration: none;
}

.message-content ::v-deep a:hover {
  text-decoration: underline;
}

.message-content ::v-deep code {
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--qd-panel-strong);
  color: var(--qd-text);
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
}

.message-content ::v-deep .qd-code-block {
  margin: 10px 0;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 8px;
  background: #0f172a;
}

.message-content ::v-deep .qd-code-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 9px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  background: #111c31;
  color: #cbd5e1;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
}

.message-content ::v-deep .qd-copy-code {
  border: 1px solid rgba(203, 213, 225, 0.24);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 4px 8px;
  transition: border-color 0.18s, background 0.18s;
}

.message-content ::v-deep .qd-copy-code:hover {
  border-color: color-mix(in srgb, var(--qd-accent) 58%, transparent);
  background: var(--qd-accent-ring);
}

.message-content ::v-deep pre {
  max-width: ~"min(760px, 70vw)";
  margin: 0;
  overflow: auto;
  padding: 12px;
}

.message-content ::v-deep pre code {
  display: block;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: #e2e8f0;
  line-height: 1.58;
  white-space: pre;
}

.message-meta {
  margin-top: 8px;
  color: var(--qd-text-subtle);
  font-size: 12px;
}

.message-time {
  margin-top: 8px;
  color: var(--qd-text-subtle);
  font-size: 11px;
  line-height: 1;
  text-align: right;
}

.message.assistant .message-time {
  text-align: left;
}

.message-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--qd-border-soft);
}

.message-actions button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 28%, transparent);
  border-radius: 6px;
  background: var(--qd-accent-soft);
  color: var(--qd-accent);
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
  transition: border-color 0.18s, background 0.18s, transform 0.18s;
}

.message-actions button:hover {
  border-color: color-mix(in srgb, var(--qd-accent) 54%, transparent);
  background: var(--qd-accent-ring);
  transform: translateY(-1px);
}

.attachment-row,
.pending-attachments {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.thumb,
.pending-thumb {
  position: relative;
  width: 96px;
  height: 64px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--qd-border);
  background: var(--qd-panel-soft);
}

.thumb img,
.pending-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pending-attachments {
  flex: 0 0 auto;
  max-height: 92px;
  overflow-y: auto;
  padding: 10px 16px 2px;
}

.pending-thumb button {
  position: absolute;
  right: 2px;
  top: 2px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.62);
  color: #fff;
}

.composer {
  flex: 0 0 auto;
  border-top: 1px solid var(--qd-border-soft);
  padding: 12px 14px;
  background: var(--qd-panel);
}

.composer textarea {
  width: 100%;
  min-height: 98px;
  max-height: 236px;
  overflow-y: hidden;
  resize: none;
  padding: 12px 13px;
  border: 1px solid var(--qd-border);
  border-radius: 8px;
  outline: none;
  background: var(--qd-panel-soft);
  color: var(--qd-text);
  line-height: 1.55;
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s;
}

.composer textarea:focus {
  border-color: color-mix(in srgb, var(--qd-accent) 58%, transparent);
  background: var(--qd-panel);
  box-shadow: 0 0 0 3px var(--qd-accent-ring);
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
}

.risk-disclaimer {
  min-width: 0;
  margin: 0;
  color: var(--qd-text-subtle);
  font-size: 12px;
  line-height: 1.45;
}

.risk-disclaimer .anticon {
  margin-right: 5px;
  color: var(--qd-accent);
}

.composer-actions {
  display: flex;
  flex: 0 0 auto;
  justify-content: flex-end;
  gap: 8px;
}

.composer-actions input[type='file'] {
  display: none;
}

.add-watch {
  display: block;
  margin-bottom: 10px;
}

.watch-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 82px;
  align-items: center;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel-soft);
  overflow: hidden;
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s, transform 0.18s;
}

.watch-card:hover {
  border-color: var(--qd-accent-border);
  background: var(--qd-panel);
  box-shadow: 0 7px 20px var(--qd-accent-weak);
  transform: translateY(-1px);
}

.watch-card.active {
  border-color: color-mix(in srgb, var(--qd-accent) 58%, transparent);
  background: var(--qd-accent-soft);
}

.watch-main {
  width: 100%;
  border: 0;
  background: transparent;
  display: grid;
  grid-template-columns: minmax(92px, 1fr) minmax(86px, auto);
  align-items: center;
  gap: 8px;
  padding: 8px 6px 8px 10px;
  cursor: pointer;
  text-align: left;
}

.watch-identity {
  min-width: 0;
}

.watch-market-data {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}

.watch-price,
.watch-change {
  display: block;
  max-width: 86px;
  overflow: hidden;
  font-family: 'SF Mono', Consolas, monospace;
  font-weight: 700;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.watch-price {
  color: var(--qd-text);
  font-size: 12px;
  line-height: 1.25;
}

.watch-change {
  width: fit-content;
  max-width: 92px;
  padding: 1px 5px;
  border-radius: 5px;
  background: rgba(107, 127, 153, 0.1);
  font-size: 11px;
  line-height: 1.2;
}

.watch-change.up {
  color: var(--qd-green);
  background: rgba(10, 163, 117, 0.12);
}

.watch-change.down {
  color: var(--qd-red);
  background: rgba(229, 75, 75, 0.12);
}

.watch-actions {
  display: flex;
  justify-content: flex-end;
  gap: 2px;
  border-left: 1px solid var(--qd-border-soft);
  padding: 0 6px;
}

.watch-actions button {
  width: 22px;
  height: 24px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #4c75a3;
  font-size: 12px;
  line-height: 24px;
  cursor: pointer;
  transition: color 0.18s, background 0.18s;
}

.watch-actions button:hover {
  color: var(--qd-accent);
  background: var(--qd-accent-weak);
}

.watch-actions button.danger:hover {
  color: var(--qd-red);
  background: rgba(229, 75, 75, 0.1);
}

.monitor-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel-soft);
}

.monitor-actions {
  display: flex;
  gap: 4px;
}

.monitor-actions button {
  width: 28px;
  height: 28px;
  border: 1px solid var(--qd-border);
  border-radius: 6px;
  background: var(--qd-panel);
  color: #66809f;
  cursor: pointer;
}

.up {
  color: var(--qd-green);
}

.down {
  color: var(--qd-red);
}

.event-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--qd-border-soft);
}

.event-title-row strong {
  display: block;
  color: var(--qd-text);
  font-size: 18px;
}

.event-title-row span {
  color: var(--qd-text-subtle);
}

.event-fields {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin: 14px 0;
}

.event-fields div {
  padding: 10px;
  border: 1px solid var(--qd-border-soft);
  border-radius: 8px;
  background: var(--qd-panel-soft);
}

.event-fields label {
  display: block;
  color: var(--qd-text-subtle);
  margin-bottom: 4px;
}

.event-ai-preview {
  padding: 12px;
  border-radius: 8px;
  background: var(--qd-accent-soft);
  color: #2f4664;
}

.event-ai-preview h4 {
  margin: 0 0 8px;
  color: var(--qd-text);
}

.add-watch-modal {
  .ant-tabs-bar {
    margin-bottom: 14px;
  }
}

.add-watch-results {
  display: grid;
  gap: 8px;
  max-height: 300px;
  margin-top: 14px;
  overflow-y: auto;
}

.symbol-result-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--qd-border-soft, #e8eff7);
  border-radius: 8px;
  background: var(--qd-panel-soft, #f7fafd);
  color: var(--qd-text, #12243d);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s;
}

.symbol-result-card:hover,
.symbol-result-card.active {
  border-color: color-mix(in srgb, var(--qd-accent) 54%, transparent);
  background: var(--qd-accent-soft);
  box-shadow: 0 6px 18px var(--qd-accent-weak);
}

.symbol-result-card strong,
.symbol-result-card em {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.symbol-result-card em {
  margin-top: 2px;
  color: var(--qd-text-subtle, #92a2b6);
  font-size: 12px;
  font-style: normal;
}

.selected-watch-alert {
  margin-top: 14px;
}

.strategy-flow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  padding: 4px 0 2px;
}

.strategy-flow-guide {
  display: none;
}

.strategy-flow-guide span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 0;
  height: 28px;
  border-radius: 6px;
  color: var(--qd-text-muted, #6b7f99);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.strategy-flow-guide .anticon {
  color: var(--qd-accent, #1677ff);
}

.strategy-flow-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  min-height: 132px;
  padding: 16px;
  border: 1px solid var(--qd-border-soft, #e8eff7);
  border-radius: 10px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--qd-panel, #fff) 88%, transparent), color-mix(in srgb, var(--qd-panel-soft, #f7fafd) 92%, transparent));
  color: var(--qd-text, #12243d);
  text-align: left;
  cursor: pointer;
  backdrop-filter: blur(14px);
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s, transform 0.18s;
}

.strategy-flow-card:hover {
  border-color: color-mix(in srgb, var(--qd-accent) 54%, transparent);
  background: var(--qd-accent-soft, #eef6ff);
  box-shadow: 0 8px 22px var(--qd-accent-ring);
  transform: translateY(-1px);
}

.strategy-flow-card > .anticon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 22%, transparent);
  border-radius: 10px;
  background: var(--qd-accent-soft);
  color: var(--qd-accent, #1677ff);
  font-size: 19px;
}

.strategy-flow-card strong,
.strategy-flow-card em {
  display: block;
}

.strategy-flow-card strong {
  margin-bottom: 7px;
  color: var(--qd-text, #12243d);
  font-size: 15px;
  font-weight: 900;
  line-height: 1.25;
}

.strategy-flow-card em {
  color: var(--qd-text-muted, #6b7f99);
  font-size: 12px;
  font-style: normal;
  line-height: 1.55;
  white-space: normal;
  word-break: normal;
  overflow-wrap: anywhere;
}

.copilot-workbench ::v-deep .ant-select-selection {
  border-color: var(--qd-border);
  border-radius: 7px;
  background: var(--qd-panel);
}

.copilot-workbench ::v-deep .ant-select-selection__placeholder,
.composer textarea::placeholder {
  color: var(--qd-text-subtle);
}

.copilot-workbench ::v-deep .ant-select-focused .ant-select-selection,
.copilot-workbench ::v-deep .ant-select-selection:focus,
.copilot-workbench ::v-deep .ant-select-selection:active {
  border-color: color-mix(in srgb, var(--qd-accent) 58%, transparent);
  box-shadow: 0 0 0 3px var(--qd-accent-ring);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

@media (max-width: 1360px) {
  .copilot-workbench {
    grid-template-columns: minmax(250px, 300px) minmax(520px, 1fr);
    overflow: auto;
    height: auto;
  }
  .right-rail {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .watch-panel,
  .monitor-panel {
    min-height: 260px;
  }
  .strategy-flow {
    grid-template-columns: 1fr;
  }
  .strategy-flow-guide,
  .workflow-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .welcome-prompts {
    grid-template-columns: repeat(2, minmax(180px, 1fr));
  }
}

@media (max-width: 960px) {
  .copilot-workbench {
    grid-template-columns: 1fr;
    min-height: auto;
  }
  .right-rail {
    display: flex;
  }
  .chat-hero {
    padding: 14px 16px;
  }
  .hero-main {
    display: block;
  }
  .context-bar {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .strategy-flow-guide,
  .workflow-steps {
    grid-template-columns: 1fr;
  }
  .workflow-head {
    display: grid;
  }
  .sessions-panel,
  .calendar-panel,
  .watch-panel,
  .monitor-panel {
    flex: 0 0 auto;
    min-height: 220px;
  }
  .chat-panel {
    min-height: 680px;
  }
  .welcome {
    margin-top: 34px;
  }
  .welcome-prompts {
    grid-template-columns: 1fr;
  }
}

/* Premium research cockpit pass */
.copilot-workbench {
  --qd-bg: #eef4fb;
  --qd-panel: rgba(255, 255, 255, 0.94);
  --qd-panel-soft: rgba(247, 250, 253, 0.9);
  --qd-panel-strong: #eef5fc;
  --qd-border: rgba(146, 162, 182, 0.28);
  --qd-border-soft: rgba(146, 162, 182, 0.18);
  --qd-shadow: 0 18px 42px rgba(21, 45, 78, 0.1);

  position: relative;
  grid-template-columns: minmax(250px, 292px) minmax(640px, 1fr) minmax(286px, 330px);
  gap: 12px;
  padding: 12px;
  isolation: isolate;
  background:
    radial-gradient(circle at 49% 26%, color-mix(in srgb, var(--qd-accent) 18%, transparent), transparent 29%),
    radial-gradient(circle at 76% 12%, rgba(20, 184, 166, 0.16), transparent 27%),
    linear-gradient(180deg, #f7fbff 0%, #edf3fa 42%, #f8fafc 100%);
}

.copilot-workbench::before {
  content: "";
  position: absolute;
  inset: 12px 324px 12px 304px;
  z-index: -1;
  border: 1px solid rgba(255, 255, 255, 0.56);
  border-radius: 12px;
  background:
    linear-gradient(rgba(22, 119, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(22, 119, 255, 0.035) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.9), transparent 72%);
  pointer-events: none;
}

.rail-panel,
.chat-panel {
  border-color: rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.075);
  backdrop-filter: blur(14px);
}

.rail-panel {
  padding: 13px;
}

.left-rail,
.right-rail {
  gap: 12px;
}

.panel-head {
  min-height: 28px;
  margin-bottom: 11px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
  font-size: 12px;
  letter-spacing: 0;
  text-transform: none;
}

.sessions-panel {
  flex-basis: 54%;
  min-height: 330px;
}

.calendar-panel {
  flex-basis: 35%;
  min-height: 230px;
}

.watch-panel {
  flex-basis: 60%;
}

.monitor-panel {
  flex-basis: 36%;
  min-height: 250px;
}

.session-row,
.calendar-card,
.watch-card,
.monitor-card {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(248, 251, 255, 0.78);
}

.session-row:hover,
.calendar-card:hover,
.watch-card:hover {
  border-color: color-mix(in srgb, var(--qd-accent) 36%, rgba(148, 163, 184, 0.26));
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 24px rgba(21, 45, 78, 0.1);
}

.chat-panel {
  position: relative;
  border-color: rgba(148, 163, 184, 0.22);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.7);
}

.chat-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(circle at 52% 18%, color-mix(in srgb, var(--qd-accent) 11%, transparent), transparent 32%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.52), rgba(255, 255, 255, 0));
  pointer-events: none;
}

.chat-hero,
.messages,
.pending-attachments,
.composer {
  position: relative;
  z-index: 1;
}

.chat-hero {
  min-height: 104px;
  padding: 18px 20px 16px;
  border-bottom-color: rgba(148, 163, 184, 0.18);
  background:
    radial-gradient(circle at 71% 0%, rgba(20, 184, 166, 0.14), transparent 34%),
    radial-gradient(circle at 36% 0%, color-mix(in srgb, var(--qd-accent) 16%, transparent), transparent 34%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(238, 246, 255, 0.7));
}

.chat-hero::after {
  content: "";
  position: absolute;
  right: 380px;
  top: 18px;
  width: 92px;
  height: 92px;
  border: 1px solid color-mix(in srgb, var(--qd-accent) 24%, transparent);
  border-radius: 50%;
  background:
    radial-gradient(circle at 35% 35%, rgba(255, 255, 255, 0.9), transparent 16%),
    radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--qd-accent) 28%, transparent), transparent 47%),
    linear-gradient(135deg, rgba(20, 184, 166, 0.26), color-mix(in srgb, var(--qd-accent) 24%, transparent));
  box-shadow: 0 18px 38px color-mix(in srgb, var(--qd-accent) 16%, transparent);
  opacity: 0.72;
  pointer-events: none;
}

.hero-main {
  grid-template-columns: minmax(0, 1fr) minmax(320px, 360px);
}

.eyebrow {
  min-height: 20px;
  margin-bottom: 7px;
  background: color-mix(in srgb, var(--qd-accent) 12%, #ffffff);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.46);
}

.chat-hero h2 {
  font-size: 24px;
  line-height: 1.18;
}

.chat-hero p {
  max-width: 700px;
  font-size: 13px;
}

.context-status {
  height: 22px;
  color: var(--qd-text-muted);
}

.hero-symbol-picker ::v-deep .ant-select-selection {
  height: 38px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
}

.hero-symbol-picker ::v-deep .ant-select-selection__rendered {
  line-height: 36px;
}

.messages {
  padding: 28px 28px 22px;
  background:
    linear-gradient(rgba(22, 119, 255, 0.028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(22, 119, 255, 0.028) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(247, 250, 253, 0.92));
  background-size: 38px 38px, 38px 38px, auto;
}

.welcome {
  max-width: 860px;
  margin-top: 46px;
}

.welcome > .anticon {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  box-shadow: 0 14px 32px color-mix(in srgb, var(--qd-accent) 18%, transparent);
}

.welcome h3 {
  margin-top: 16px;
  font-size: 25px;
}

.welcome p {
  max-width: 620px;
  margin: 0 auto;
  font-size: 13px;
  line-height: 1.7;
}

.welcome-prompts {
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 12px;
  margin-top: 24px;
}

.welcome-prompts button {
  min-height: 84px;
  padding: 14px;
  border-color: rgba(148, 163, 184, 0.24);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.82), color-mix(in srgb, var(--qd-accent) 7%, #f8fbff));
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.055);
}

.welcome-prompts button:hover {
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.1);
  transform: translateY(-2px);
}

.task-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
}

.task-copy strong {
  font-size: 13px;
}

.task-copy em {
  color: var(--qd-text-subtle);
}

.bubble {
  max-width: ~"min(900px, 76%)";
  border-color: rgba(148, 163, 184, 0.24);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.075);
}

.message.user .bubble {
  background: color-mix(in srgb, var(--qd-accent) 12%, #ffffff);
}

.composer {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
}

.composer textarea {
  min-height: 98px;
  border-radius: 8px;
  background: rgba(247, 250, 253, 0.92);
}

.composer-actions ::v-deep .ant-btn,
.add-watch ::v-deep .ant-btn {
  height: 34px;
  border-radius: 8px;
}

.add-watch {
  margin-bottom: 12px;
}

.watch-main {
  padding: 9px 8px 9px 11px;
}

.watch-actions {
  opacity: 0.72;
  transition: opacity 0.18s;
}

.watch-card:hover .watch-actions {
  opacity: 1;
}

@media (max-width: 1360px) {
  .copilot-workbench {
    grid-template-columns: minmax(250px, 300px) minmax(580px, 1fr);
  }

  .copilot-workbench::before {
    inset: 12px;
  }

  .chat-hero::after {
    right: 30px;
    opacity: 0.34;
  }
}

@media (max-width: 960px) {
  .copilot-workbench {
    padding: 10px;
  }

  .chat-hero {
    min-height: 0;
  }

  .chat-hero::after {
    display: none;
  }
}

/* Final AI workbench tune-up for the conversation-first redesign. */
.copilot-workbench {
  padding: 8px;
  background:
    radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--qd-accent) 12%, transparent), transparent 28%),
    linear-gradient(180deg, #f5f9fd 0%, #eef4fa 100%);
}

.copilot-workbench .chat-panel,
.copilot-workbench .rail-panel {
  border-color: rgba(129, 151, 178, 0.22);
  background: rgba(255, 255, 255, 0.68);
  box-shadow: 0 16px 38px rgba(31, 62, 103, 0.1);
  -webkit-backdrop-filter: blur(18px) saturate(1.16);
  backdrop-filter: blur(18px) saturate(1.16);
}

.copilot-workbench .chat-hero {
  min-height: 56px !important;
  padding: 8px 16px !important;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.86), rgba(247, 251, 255, 0.62)),
    rgba(255, 255, 255, 0.56) !important;
}

.copilot-workbench .hero-main {
  grid-template-columns: minmax(0, 1fr) minmax(300px, 390px);
  gap: 14px;
}

.copilot-workbench .eyebrow {
  min-height: 16px;
  margin-bottom: 2px;
  padding: 0 7px;
  font-size: 10px;
}

.copilot-workbench .chat-hero h2 {
  margin: 0 0 1px;
  font-size: 18px;
  line-height: 1.12;
}

.copilot-workbench .chat-hero p {
  font-size: 12px;
  line-height: 1.28;
}

.copilot-workbench .context-status {
  height: 16px;
  font-size: 11px;
}

.copilot-workbench .hero-symbol-picker ::v-deep .ant-select-selection {
  height: 31px !important;
}

.copilot-workbench .hero-symbol-picker ::v-deep .ant-select-selection__rendered {
  line-height: 29px !important;
}

.copilot-workbench .messages {
  padding-top: 18px;
}

.copilot-workbench .welcome {
  max-width: 920px;
  margin-top: clamp(72px, 10vh, 118px);
}

.copilot-workbench .welcome > .anticon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  font-size: 20px;
}

.copilot-workbench .welcome h3 {
  margin: 10px 0 4px;
  font-size: 20px;
}

.copilot-workbench .welcome-prompts {
  grid-template-columns: repeat(4, minmax(170px, 1fr));
  max-width: 900px;
  gap: 12px;
}

.copilot-workbench .welcome-prompts button {
  min-height: 76px !important;
  padding: 12px;
  border-radius: 10px;
}


.copilot-workbench .message-actions {
  border-top: 1px solid var(--qd-border-soft);
}

.strategy-flow {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 14px !important;
  padding: 2px 0 0 !important;
}

.strategy-flow-guide {
  display: none !important;
}

.strategy-flow-card {
  display: grid !important;
  grid-template-columns: 42px minmax(0, 1fr) !important;
  align-items: flex-start !important;
  min-height: 130px !important;
  padding: 16px !important;
  border-radius: 10px !important;
  white-space: normal !important;
}

.strategy-flow-card strong,
.strategy-flow-card em {
  white-space: normal !important;
  word-break: normal !important;
  overflow-wrap: anywhere !important;
}

body.dark .copilot-workbench,
body.realdark .copilot-workbench,
.theme-dark .copilot-workbench {
  --qd-bg: #050505;
  --qd-panel: #0b0b0b;
  --qd-panel-soft: #111111;
  --qd-panel-strong: #161616;
  --qd-text: #f4f7fb;
  --qd-text-muted: #9ba7b7;
  --qd-text-subtle: #718096;
  --qd-border: rgba(255, 255, 255, 0.12);
  --qd-border-soft: rgba(255, 255, 255, 0.08);
  background: #050505 !important;
}

body.dark .copilot-workbench .chat-panel,
body.realdark .copilot-workbench .chat-panel,
.theme-dark .copilot-workbench .chat-panel,
body.dark .copilot-workbench .rail-panel,
body.realdark .copilot-workbench .rail-panel,
.theme-dark .copilot-workbench .rail-panel {
  background: #0b0b0b !important;
  box-shadow: none !important;
}

body.dark .copilot-workbench .chat-hero,
body.realdark .copilot-workbench .chat-hero,
.theme-dark .copilot-workbench .chat-hero {
  background: #0d0d0d !important;
}

body.dark .copilot-workbench .chat-panel::before,
body.dark .copilot-workbench::before,
body.dark .copilot-workbench .chat-hero::after,
body.realdark .copilot-workbench .chat-panel::before,
body.realdark .copilot-workbench::before,
body.realdark .copilot-workbench .chat-hero::after,
.theme-dark .copilot-workbench .chat-panel::before,
.theme-dark .copilot-workbench::before,
.theme-dark .copilot-workbench .chat-hero::after {
  display: none !important;
}

body.dark .copilot-workbench .messages,
body.realdark .copilot-workbench .messages,
.theme-dark .copilot-workbench .messages {
  background: #080808 !important;
}

body.dark .copilot-workbench .session-row,
body.dark .copilot-workbench .calendar-card,
body.dark .copilot-workbench .watch-card,
body.dark .copilot-workbench .monitor-card,
body.dark .copilot-workbench .welcome-prompts button,
body.dark .copilot-workbench .strategy-flow-card,
body.realdark .copilot-workbench .session-row,
body.realdark .copilot-workbench .calendar-card,
body.realdark .copilot-workbench .watch-card,
body.realdark .copilot-workbench .monitor-card,
body.realdark .copilot-workbench .welcome-prompts button,
body.realdark .copilot-workbench .strategy-flow-card,
.theme-dark .copilot-workbench .session-row,
.theme-dark .copilot-workbench .calendar-card,
.theme-dark .copilot-workbench .watch-card,
.theme-dark .copilot-workbench .monitor-card,
.theme-dark .copilot-workbench .welcome-prompts button,
.theme-dark .copilot-workbench .strategy-flow-card {
  border-color: rgba(255, 255, 255, 0.11) !important;
  background: #141414 !important;
  box-shadow: none !important;
}

body.dark .copilot-workbench .session-row:hover,
body.dark .copilot-workbench .calendar-card:hover,
body.dark .copilot-workbench .watch-card:hover,
body.dark .copilot-workbench .welcome-prompts button:hover,
body.realdark .copilot-workbench .session-row:hover,
body.realdark .copilot-workbench .calendar-card:hover,
body.realdark .copilot-workbench .watch-card:hover,
body.realdark .copilot-workbench .welcome-prompts button:hover,
.theme-dark .copilot-workbench .session-row:hover,
.theme-dark .copilot-workbench .calendar-card:hover,
.theme-dark .copilot-workbench .watch-card:hover,
.theme-dark .copilot-workbench .welcome-prompts button:hover {
  border-color: color-mix(in srgb, var(--qd-accent) 42%, rgba(255, 255, 255, 0.14)) !important;
  background: #191919 !important;
}

body.dark .copilot-workbench .session-row.active,
body.dark .copilot-workbench .watch-card.active,
body.realdark .copilot-workbench .session-row.active,
body.realdark .copilot-workbench .watch-card.active,
.theme-dark .copilot-workbench .session-row.active,
.theme-dark .copilot-workbench .watch-card.active {
  border-color: color-mix(in srgb, var(--qd-accent) 70%, rgba(255, 255, 255, 0.14)) !important;
  background: color-mix(in srgb, var(--qd-accent) 16%, #141414) !important;
}

body.dark .copilot-workbench .bubble,
body.realdark .copilot-workbench .bubble,
.theme-dark .copilot-workbench .bubble {
  border-color: rgba(255, 255, 255, 0.12) !important;
  background: #121212 !important;
  color: var(--qd-text) !important;
  box-shadow: none !important;
}

body.dark .copilot-workbench .message.user .bubble,
body.realdark .copilot-workbench .message.user .bubble,
.theme-dark .copilot-workbench .message.user .bubble {
  background: color-mix(in srgb, var(--qd-accent) 20%, #111111) !important;
}

body.dark .copilot-workbench .composer,
body.realdark .copilot-workbench .composer,
.theme-dark .copilot-workbench .composer {
  border-top-color: rgba(255, 255, 255, 0.1) !important;
  background: #0b0b0b !important;
}

body.dark .copilot-workbench .composer textarea,
body.realdark .copilot-workbench .composer textarea,
.theme-dark .copilot-workbench .composer textarea {
  border-color: rgba(255, 255, 255, 0.14) !important;
  background: #101010 !important;
  color: var(--qd-text) !important;
}

body.dark .copilot-workbench .empty-mini,
body.realdark .copilot-workbench .empty-mini,
.theme-dark .copilot-workbench .empty-mini {
  border-color: rgba(255, 255, 255, 0.1) !important;
  background: #141414 !important;
  color: var(--qd-text-muted) !important;
}

@media (max-width: 1360px) {
  .strategy-flow {
    grid-template-columns: 1fr !important;
  }
}

@media (max-width: 960px) {
  .copilot-workbench .hero-main,
  .copilot-workbench .welcome-prompts {
    grid-template-columns: 1fr;
  }

  .composer-foot {
    align-items: stretch;
    flex-direction: column;
  }

  .composer-actions {
    justify-content: flex-end;
  }
}

@media print {
  .copilot-workbench {
    display: block !important;
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
    padding: 0 !important;
    background: #fff !important;
  }

  .copilot-workbench > .left-rail,
  .copilot-workbench > .right-rail,
  .copilot-workbench .chat-hero,
  .copilot-workbench .composer,
  .copilot-workbench .welcome,
  .copilot-workbench .message:not(.printing-report-message),
  .copilot-workbench .printing-report-message .avatar,
  .copilot-workbench .printing-report-message .message-content,
  .copilot-workbench .printing-report-message .message-meta,
  .copilot-workbench .printing-report-message .message-actions,
  .copilot-workbench .printing-report-message .message-time {
    display: none !important;
  }

  .copilot-workbench .chat-panel,
  .copilot-workbench .messages,
  .copilot-workbench .printing-report-message,
  .copilot-workbench .printing-report-message .bubble,
  .copilot-workbench .copilot-report-card {
    display: block !important;
    width: 100% !important;
    max-width: none !important;
    height: auto !important;
    overflow: visible !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    box-shadow: none !important;
    background: #fff !important;
  }
}
</style>

<style lang="less">
.add-watch-copilot-modal {
  .ant-modal-content,
  .ant-modal-header,
  .ant-modal-footer {
    background: var(--qd-panel, #fff);
    border-color: var(--qd-border-soft, #e8eff7);
  }

  .ant-modal-title,
  .ant-modal-close,
  .ant-modal-close-x,
  .ant-tabs-tab,
  .ant-input,
  .ant-input-search-button {
    color: var(--qd-text, #12243d);
  }

  .ant-input {
    background: var(--qd-panel-soft, #f7fafd);
    border-color: var(--qd-border-soft, #e8eff7);
  }

  .ant-tabs-bar {
    border-bottom-color: var(--qd-border-soft, #e8eff7);
  }

  .ant-tabs-tab:hover,
  .ant-tabs-tab-active {
    color: var(--qd-accent, #1677ff);
  }

  .ant-tabs-ink-bar {
    background: var(--qd-accent, #1677ff);
  }

  .symbol-result-card {
    border-color: var(--qd-border-soft, #e8eff7);
    background: var(--qd-panel-soft, #f7fafd);
    color: var(--qd-text, #12243d);
  }

  .symbol-result-card em {
    color: var(--qd-text-subtle, #92a2b6);
  }

  .add-watch-results {
    scrollbar-color: var(--qd-text-subtle, #92a2b6) transparent;
  }
}

body.dark .add-watch-copilot-modal,
body.realdark .add-watch-copilot-modal,
.theme-dark .add-watch-copilot-modal {
  --qd-panel: #161616;
  --qd-panel-soft: #101010;
  --qd-border-soft: rgba(255, 255, 255, 0.12);
  --qd-text: #e7edf6;
  --qd-text-muted: #9ba6b8;
  --qd-text-subtle: #7d8798;
  --qd-accent: var(--primary-color, #3b6bff);
  --qd-accent-soft: color-mix(in srgb, var(--qd-accent) 16%, #111111);

  .ant-modal-content,
  .ant-modal-header,
  .ant-modal-footer {
    background: #161616 !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
  }

  .ant-modal-title,
  .ant-modal-close,
  .ant-modal-close-x,
  .ant-tabs-tab {
    color: #dbe4f0 !important;
  }

  .ant-input {
    background: #101010 !important;
    border-color: rgba(255, 255, 255, 0.14) !important;
    color: #e7edf6 !important;
  }

  .ant-input::placeholder {
    color: #687386 !important;
  }

  .ant-tabs-bar {
    border-bottom-color: rgba(255, 255, 255, 0.1) !important;
  }

  .symbol-result-card {
    border-color: rgba(255, 255, 255, 0.11) !important;
    background: #111827 !important;
    color: #e7edf6 !important;
  }

  .symbol-result-card:hover,
  .symbol-result-card.active {
    border-color: color-mix(in srgb, var(--qd-accent) 62%, rgba(255, 255, 255, 0.12)) !important;
    background: color-mix(in srgb, var(--qd-accent) 15%, #111827) !important;
  }

  .symbol-result-card em {
    color: #8a96a8 !important;
  }
}
</style>
