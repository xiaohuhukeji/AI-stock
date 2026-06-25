"""
A-share stock screener API routes.
"""

from flask import g, jsonify, request
from app.openapi.blueprint import HumanBlueprint as Blueprint
import time

from app.utils.auth import login_required
from app.utils.logger import get_logger
from app.services.cn_stock_screener import get_stock_screener_service
from app.services.llm import LLMService
from app.services.billing_service import get_billing_service

logger = get_logger(__name__)

screener_blp = Blueprint('stock_screener', __name__)


@screener_blp.route('/screen', methods=['POST'])
@login_required
def screen_stocks():
    """
    条件选股
    """
    try:
        data = request.get_json() or {}

        params = {
            'universe': data.get('universe', 'hs300'),
            'custom_codes': data.get('custom_codes', []),
            'pe_min': data.get('pe_min'),
            'pe_max': data.get('pe_max'),
            'pb_min': data.get('pb_min'),
            'pb_max': data.get('pb_max'),
            'roe_min': data.get('roe_min'),
            'revenue_growth_min': data.get('revenue_growth_min'),
            'above_ma20': data.get('above_ma20', False),
            'above_ma60': data.get('above_ma60', False),
            'ma_bullish': data.get('ma_bullish', False),
            'volume_surged': data.get('volume_surged', False),
            'high_turnover': data.get('high_turnover', False),
            'change_min': data.get('change_min'),
            'sectors': data.get('sectors', []),
        }

        service = get_stock_screener_service()
        result = service.screen_stocks(params)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Stock screener error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@screener_blp.route('/ai-screen', methods=['POST'])
@login_required
def ai_screen_stocks():
    """
    AI 智能选股
    """
    try:
        data = request.get_json() or {}
        prompt = data.get('prompt', '')

        if not prompt or not prompt.strip():
            return jsonify({
                'success': False,
                'error': '请输入选股需求'
            }), 400

        user_id = g.user_id

        # 扣费检查
        billing = get_billing_service()
        success, msg = billing.check_and_consume(user_id, 'ai_stock_screener')
        if not success:
            return jsonify({
                'success': False,
                'error': msg or '积分不足，请先充值',
                'code': 'INSUFFICIENT_CREDITS'
            }), 402

        # 1. 使用 AI 解析选股条件
        import json
        import re

        llm = LLMService()
        system_prompt = """你是一个专业的A股量化选股分析师。请根据用户的自然语言描述，提取出具体的选股条件。

请严格按照以下JSON格式返回（不要包含任何其他文字）：
{
  "universe": "hs300",
  "pe_min": null,
  "pe_max": null,
  "pb_min": null,
  "pb_max": null,
  "roe_min": null,
  "revenue_growth_min": null,
  "change_min": null,
  "sectors": [],
  "analysis_summary": "选股逻辑的简要说明"
}

股票池选项 (universe):
- hs300: 沪深300
- sz50: 上证50
- zz500: 中证500
- cyb: 创业板

行业板块选项 (sectors):
银行、保险、证券、白酒、医药、新能源、半导体、人工智能、房地产、基建、消费、家电、汽车、有色金属、煤炭、石油

如果用户没有明确提到某个条件，对应字段设为null。"""

        ai_text = llm.call_llm_api(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.3,
            use_json_mode=True
        )

        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', ai_text)
        screen_params = {}
        analysis_summary = ''

        if json_match:
            try:
                parsed = json.loads(json_match.group())
                screen_params = parsed
                analysis_summary = parsed.get('analysis_summary', '')
            except json.JSONDecodeError:
                pass

        if not screen_params:
            screen_params = {'universe': 'hs300'}
            analysis_summary = 'AI解析失败，使用默认选股条件'

        # 3. 执行选股
        service = get_stock_screener_service()
        screen_result = service.screen_stocks(screen_params)

        # 4. 生成 AI 分析报告
        top_stocks = screen_result['stocks'][:5]
        stock_list_str = '\n'.join([
            f"{i+1}. {s['name']}({s['symbol']}) - 评分:{s['score']}分, PE:{s['pe']:.1f}, ROE:{s['roe']:.1f}%"
            for i, s in enumerate(top_stocks)
        ])

        report_prompt = f"""根据以下选股结果，为用户生成一份简洁的A股选股分析报告：

用户需求：{prompt}

选股结果（前5名）：
{stock_list_str}

请用中文生成分析报告，包括：
1. 选股逻辑总结
2. 推荐标的分析（重点前3名）
3. 风险提示

字数控制在300字左右，使用Markdown格式。"""

        report_response = llm.call_llm_api(
            messages=[
                {'role': 'system', 'content': '你是专业的A股投资分析师，擅长基本面分析和量化选股。'},
                {'role': 'user', 'content': report_prompt}
            ],
            temperature=0.7
        )

        analysis_text = report_response

        return jsonify({
            'success': True,
            'data': {
                'analysis': analysis_text,
                'stocks': screen_result['stocks'],
                'total': screen_result['total'],
                'params': screen_params
            }
        })

    except Exception as e:
        logger.error(f"AI stock screener error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@screener_blp.route('/universes', methods=['GET'])
@login_required
def get_universes():
    """获取股票池列表"""
    return jsonify({
        'success': True,
        'data': [
            {'key': 'hs300', 'label': '沪深300'},
            {'key': 'sz50', 'label': '上证50'},
            {'key': 'zz500', 'label': '中证500'},
            {'key': 'cyb', 'label': '创业板'},
            {'key': 'custom', 'label': '自定义'},
        ]
    })


@screener_blp.route('/sectors', methods=['GET'])
@login_required
def get_sectors():
    """获取行业板块列表"""
    sectors = [
        '银行', '保险', '证券', '白酒', '医药', '新能源',
        '半导体', '人工智能', '房地产', '基建', '消费', '家电',
        '汽车', '有色金属', '煤炭', '石油'
    ]
    return jsonify({
        'success': True,
        'data': sectors
    })
