const l=[{key:"trailingStop",icon:"🪤",accent:"violet",code:`"""
Trailing Stop Strategy
Enter on EMA crossover, manage exits with a hard stop and a trailing stop
that arms only after a minimum profit threshold is reached.
"""

def on_init(ctx):
    ctx.fast_period = ctx.param('fast_period', 10)
    ctx.slow_period = ctx.param('slow_period', 30)
    ctx.position_pct = ctx.param('position_pct', 0.8)
    ctx.hard_stop_pct = ctx.param('hard_stop_pct', 0.025)
    ctx.trailing_stop_pct = ctx.param('trailing_stop_pct', 0.015)
    ctx.trailing_arm_pct = ctx.param('trailing_arm_pct', 0.02)
    ctx.peak_price = 0.0
    ctx.trailing_armed = False

def _ema(values, period):
    k = 2.0 / (period + 1)
    e = float(values[0])
    for v in values[1:]:
        e = float(v) * k + e * (1 - k)
    return e

def on_bar(ctx, bar):
    bars = ctx.bars(ctx.slow_period + 5)
    if len(bars) < ctx.slow_period:
        return
    closes = [b['close'] for b in bars]
    prev_fast = _ema(closes[:-1], ctx.fast_period)
    prev_slow = _ema(closes[:-1], ctx.slow_period)
    fast = _ema(closes, ctx.fast_period)
    slow = _ema(closes, ctx.slow_period)
    cross_up = prev_fast <= prev_slow and fast > slow
    price = bar['close']

    if not ctx.position and cross_up:
        qty = (ctx.equity * ctx.position_pct) / price
        ctx.open_long(amount=qty, price=price)
        ctx.peak_price = price
        ctx.trailing_armed = False
        ctx.log(f"BUY at {price:.2f}")
        return

    if ctx.position and ctx.position['side'] == 'long':
        entry = ctx.position['entry_price']
        ctx.peak_price = max(ctx.peak_price, price)
        pnl_pct = (price - entry) / entry

        if pnl_pct <= -ctx.hard_stop_pct:
            ctx.close_position()
            ctx.log(f"HARD STOP at {price:.2f} ({pnl_pct*100:.2f}%)")
            return

        if not ctx.trailing_armed and pnl_pct >= ctx.trailing_arm_pct:
            ctx.trailing_armed = True
            ctx.log(f"Trailing armed at {price:.2f}")

        if ctx.trailing_armed:
            trail_stop = ctx.peak_price * (1 - ctx.trailing_stop_pct)
            if price <= trail_stop:
                ctx.close_position()
                ctx.log(f"TRAILING STOP at {price:.2f} (peak {ctx.peak_price:.2f})")
`,params:[{name:"fast_period",type:"integer",default:10,min:2,max:120,step:1},{name:"slow_period",type:"integer",default:30,min:5,max:240,step:1},{name:"position_pct",type:"percent",default:80,min:5,max:100,step:1},{name:"hard_stop_pct",type:"percent",default:2.5,min:.1,max:50,step:.1},{name:"trailing_stop_pct",type:"percent",default:1.5,min:.1,max:50,step:.1},{name:"trailing_arm_pct",type:"percent",default:2,min:.1,max:50,step:.1}]},{key:"scaleInOnDip",icon:"🪜",accent:"teal",code:`"""
Scale-in on dip Strategy
Build a position in tranches as price keeps falling below the entry,
then exit with a take-profit measured against the average cost.
"""

def on_init(ctx):
    ctx.entry_pct = ctx.param('entry_pct', 0.25)
    ctx.dip_step_pct = ctx.param('dip_step_pct', 0.02)
    ctx.max_layers = ctx.param('max_layers', 4)
    ctx.take_profit_pct = ctx.param('take_profit_pct', 0.04)
    ctx.hard_stop_pct = ctx.param('hard_stop_pct', 0.10)
    ctx.entry_anchor = 0.0
    ctx.layers = 0
    ctx.avg_cost = 0.0

def _trigger_open(ctx, bar):
    bars = ctx.bars(20)
    if len(bars) < 5:
        return False
    return bar['close'] < bars[-2]['close']

def on_bar(ctx, bar):
    price = bar['close']

    if not ctx.position:
        if _trigger_open(ctx, bar):
            qty = (ctx.equity * ctx.entry_pct) / price
            ctx.open_long(amount=qty, price=price)
            ctx.entry_anchor = price
            ctx.layers = 1
            ctx.avg_cost = price
            ctx.log(f"OPEN layer 1 at {price:.2f}")
        return

    if ctx.position['side'] != 'long':
        return

    entry = ctx.position['entry_price']
    pnl_pct = (price - entry) / entry

    if pnl_pct <= -ctx.hard_stop_pct:
        ctx.close_position()
        ctx.layers = 0
        ctx.log(f"HARD STOP at {price:.2f}")
        return

    next_trigger = ctx.entry_anchor * (1 - ctx.dip_step_pct * ctx.layers)
    if ctx.layers < ctx.max_layers and price <= next_trigger:
        qty = (ctx.equity * ctx.entry_pct) / price
        ctx.add_long(amount=qty, price=price)
        ctx.layers += 1
        ctx.avg_cost = (ctx.avg_cost * (ctx.layers - 1) + price) / ctx.layers
        ctx.log(f"SCALE IN layer {ctx.layers} at {price:.2f}, avg {ctx.avg_cost:.2f}")
        return

    if ctx.avg_cost > 0 and price >= ctx.avg_cost * (1 + ctx.take_profit_pct):
        ctx.close_position()
        ctx.log(f"TAKE PROFIT at {price:.2f} (avg {ctx.avg_cost:.2f})")
        ctx.layers = 0
`,params:[{name:"entry_pct",type:"percent",default:25,min:1,max:100,step:1},{name:"dip_step_pct",type:"percent",default:2,min:.1,max:50,step:.1},{name:"max_layers",type:"integer",default:4,min:1,max:10,step:1},{name:"take_profit_pct",type:"percent",default:4,min:.1,max:100,step:.1},{name:"hard_stop_pct",type:"percent",default:10,min:.5,max:90,step:.5}]},{key:"takeProfitLadder",icon:"🎯",accent:"amber",code:`"""
Take-Profit Ladder Strategy
Enter on EMA crossover, then partially close the position at three
ascending take-profit levels. A hard stop protects the runner.
"""

def on_init(ctx):
    ctx.fast_period = ctx.param('fast_period', 10)
    ctx.slow_period = ctx.param('slow_period', 30)
    ctx.position_pct = ctx.param('position_pct', 0.9)
    ctx.tp1_pct = ctx.param('tp1_pct', 0.02)
    ctx.tp2_pct = ctx.param('tp2_pct', 0.05)
    ctx.tp3_pct = ctx.param('tp3_pct', 0.10)
    ctx.tp1_close = ctx.param('tp1_close', 0.4)
    ctx.tp2_close = ctx.param('tp2_close', 0.4)
    ctx.hard_stop_pct = ctx.param('hard_stop_pct', 0.03)
    ctx.tp_hits = 0
    ctx.original_qty = 0.0

def _ema(values, period):
    k = 2.0 / (period + 1)
    e = float(values[0])
    for v in values[1:]:
        e = float(v) * k + e * (1 - k)
    return e

def on_bar(ctx, bar):
    bars = ctx.bars(ctx.slow_period + 5)
    if len(bars) < ctx.slow_period:
        return
    closes = [b['close'] for b in bars]
    prev_fast = _ema(closes[:-1], ctx.fast_period)
    prev_slow = _ema(closes[:-1], ctx.slow_period)
    fast = _ema(closes, ctx.fast_period)
    slow = _ema(closes, ctx.slow_period)
    cross_up = prev_fast <= prev_slow and fast > slow
    price = bar['close']

    if not ctx.position and cross_up:
        qty = (ctx.equity * ctx.position_pct) / price
        ctx.open_long(amount=qty, price=price)
        ctx.original_qty = qty
        ctx.tp_hits = 0
        ctx.log(f"BUY at {price:.2f}, qty {qty:.4f}")
        return

    if not (ctx.position and ctx.position['side'] == 'long'):
        return

    entry = ctx.position['entry_price']
    pnl_pct = (price - entry) / entry

    if pnl_pct <= -ctx.hard_stop_pct:
        ctx.close_position()
        ctx.tp_hits = 0
        ctx.log(f"HARD STOP at {price:.2f}")
        return

    if ctx.tp_hits == 0 and pnl_pct >= ctx.tp1_pct:
        sell_qty = ctx.original_qty * ctx.tp1_close
        ctx.close_long(amount=sell_qty, price=price)
        ctx.tp_hits = 1
        ctx.log(f"TP1 at {price:.2f}, closed {ctx.tp1_close*100:.0f}%")
    elif ctx.tp_hits == 1 and pnl_pct >= ctx.tp2_pct:
        sell_qty = ctx.original_qty * ctx.tp2_close
        ctx.close_long(amount=sell_qty, price=price)
        ctx.tp_hits = 2
        ctx.log(f"TP2 at {price:.2f}, closed {ctx.tp2_close*100:.0f}%")
    elif ctx.tp_hits == 2 and pnl_pct >= ctx.tp3_pct:
        ctx.close_position()
        ctx.tp_hits = 3
        ctx.log(f"TP3 at {price:.2f}, runner closed")
`,params:[{name:"fast_period",type:"integer",default:10,min:2,max:120,step:1},{name:"slow_period",type:"integer",default:30,min:5,max:240,step:1},{name:"position_pct",type:"percent",default:90,min:5,max:100,step:1},{name:"tp1_pct",type:"percent",default:2,min:.1,max:100,step:.1},{name:"tp2_pct",type:"percent",default:5,min:.1,max:100,step:.1},{name:"tp3_pct",type:"percent",default:10,min:.1,max:200,step:.1},{name:"tp1_close",type:"percent",default:40,min:5,max:100,step:1},{name:"tp2_close",type:"percent",default:40,min:5,max:100,step:1},{name:"hard_stop_pct",type:"percent",default:3,min:.1,max:50,step:.1}]}];function _(e){return String(e).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}function s(e){const t=Number(e);return Number.isFinite(t)?t>0&&t<=1?t*100:t:null}function x(e){const t=s(e);return t==null?0:t/100}function u(e){const t=String(e??"").trim();if(!t)return"";if(t==="True")return!0;if(t==="False")return!1;if(t==="None")return null;const r=t[0];if((r==='"'||r==="'")&&t[t.length-1]===r)return t.slice(1,-1);const n=Number(t);return Number.isFinite(n)?n:t}function y(e,t){const r=String(e||"").toLowerCase();return/(pct|percent|ratio|allocation|weight|position|take_profit|stop|arm|entry)/.test(r)?typeof t=="number":!1}function g(e,t){return typeof t=="boolean"?"boolean":y(e,t)?"percent":Number.isInteger(t)?"integer":typeof t=="number"?"number":"text"}function b(e,t,r){if(r==="percent")return{default:s(t)??0,min:0,max:100,step:.1};if(r==="integer"){const n=String(e||"").toLowerCase();return{default:Number.isFinite(t)?t:1,min:n.includes("period")||n.includes("window")?1:void 0,max:n.includes("period")||n.includes("window")?500:void 0,step:1}}return r==="number"?{default:Number.isFinite(t)?t:0,step:.1}:{default:t??""}}function w(e){const t=String(e||""),r=/ctx\.param\(\s*['"]([^'"]+)['"]\s*,\s*([^)\n]+)\)/g,n=new Set,c=[];let p;for(;(p=r.exec(t))!==null;){const a=String(p[1]||"").trim();if(!a||n.has(a))continue;n.add(a);const i=u(p[2]),o=g(a,i);c.push({name:a,type:o,...b(a,i,o)})}return c.length?{key:"__code_params__",inferred:!0,params:c}:null}function f(e){return typeof e=="boolean"?e?"True":"False":typeof e=="number"?Number.isFinite(e)?String(e):"0":e==null?"None":`'${String(e).replace(/\\/g,"\\\\").replace(/'/g,"\\'")}'`}const k=l;function m(e){return l.find(t=>t.key===e)||null}function h(e,t={}){const r=typeof e=="string"?m(e):e;return r?r.params.reduce((n,c)=>{const p=Object.prototype.hasOwnProperty.call(t,c.name)?t[c.name]:c.default;return c.type==="percent"?n[c.name]=s(p)??c.default:n[c.name]=p,n},{}):{}}function P(e,t={}){const r=typeof e=="string"?m(e):e;if(!r)return"";const n=h(r,t);return r.params.reduce((c,p)=>{const a=n[p.name],i=p.type==="percent"?x(a):a,o=f(i),d=new RegExp(`(ctx\\.param\\(['"]${_(p.name)}['"],\\s*)([^\\)]+)(\\))`);return c.replace(d,`$1${o}$3`)},r.code)}function T(e,t=[],r={}){return(t||[]).reduce((n,c)=>{if(!c||!c.name)return n;const p=Object.prototype.hasOwnProperty.call(r,c.name)?r[c.name]:c.default,a=c.type==="percent"?x(p):p,i=f(a),o=new RegExp(`(ctx\\.param\\(\\s*['"]${_(c.name)}['"]\\s*,\\s*)([^\\)\\n]+)(\\))`);return n.replace(o,`$1${i}$3`)},String(e||""))}export{k as S,P as a,h as b,T as c,w as e,m as g,s as n};
