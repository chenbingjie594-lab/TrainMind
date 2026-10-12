<template>
  <div class="assistant-page">
    <section class="assistant-hero">
      <div>
        <div class="eyebrow"><span></span> TrainMind AI</div>
        <h1>智能出行助手</h1>
        <p>告诉我你的出发地、目的地和时间偏好，我来帮你筛选合适的车次。</p>
      </div>
      <div class="hero-status">
        <span class="status-dot"></span>
        AI 服务在线
      </div>
    </section>

    <div class="assistant-layout">
      <section class="chat-panel">
        <div class="chat-toolbar">
          <div>
            <strong>行程咨询</strong>
            <span v-if="conversationId">会话 {{ shortConversationId }}</span>
          </div>
          <a-button type="text" :disabled="sending" @click="resetConversation">
            <template #icon><plus-outlined /></template>
            新对话
          </a-button>
        </div>

        <div class="message-list">
          <div v-if="messages.length === 0" class="empty-state">
            <div class="bot-avatar large"><robot-outlined /></div>
            <h2>今天想去哪里？</h2>
            <p>你可以用自然语言描述完整需求，也可以分几次告诉我。</p>
            <div class="starter-grid">
              <button
                  v-for="item in starters"
                  :key="item.title"
                  class="starter-card"
                  @click="useStarter(item.prompt)"
              >
                <component :is="item.icon" />
                <span>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.description }}</small>
                </span>
                <arrow-right-outlined />
              </button>
            </div>
          </div>

          <template v-for="item in messages" :key="item.id">
            <div :class="['message-row', item.role]">
              <div v-if="item.role === 'assistant'" class="bot-avatar">
                <robot-outlined />
              </div>
              <div class="message-content">
                <div class="message-bubble">{{ item.content }}</div>

                <div v-if="item.constraints" class="constraint-list">
                  <span v-if="item.constraints.date"><calendar-outlined /> {{ item.constraints.date }}</span>
                  <span v-if="item.constraints.start || item.constraints.end">
                    <environment-outlined />
                    {{ item.constraints.start || '待补充' }} → {{ item.constraints.end || '待补充' }}
                  </span>
                  <span v-if="seatLabel(item.constraints)"><idcard-outlined /> {{ seatLabel(item.constraints) }}</span>
                  <span v-if="item.constraints.maxPrice"><pay-circle-outlined /> ≤ ¥{{ item.constraints.maxPrice }}</span>
                </div>

                <div v-if="item.tickets && item.tickets.length" class="ticket-list">
                  <article v-for="ticket in item.tickets" :key="ticket.trainCode" class="ticket-card">
                    <div class="train-code">
                      <span>{{ ticket.trainCode }}</span>
                      <small>{{ ticket.recommendation || '当前有可售席位' }}</small>
                    </div>
                    <div class="journey-time">
                      <div>
                        <strong>{{ formatTime(ticket.startTime) }}</strong>
                        <span>{{ ticket.start }}</span>
                      </div>
                      <div class="journey-line">
                        <span></span><car-outlined /><span></span>
                        <small>直达</small>
                      </div>
                      <div>
                        <strong>{{ formatTime(ticket.endTime) }}</strong>
                        <span>{{ ticket.end }}</span>
                      </div>
                    </div>
                    <div class="seat-summary">
                      <span v-if="available(ticket.edz)">二等座 {{ ticket.edz }} 张 · <b>¥{{ ticket.edzPrice }}</b></span>
                      <span v-if="available(ticket.ydz)">一等座 {{ ticket.ydz }} 张 · <b>¥{{ ticket.ydzPrice }}</b></span>
                      <span v-if="available(ticket.rw)">软卧 {{ ticket.rw }} 张 · <b>¥{{ ticket.rwPrice }}</b></span>
                      <span v-if="available(ticket.yw)">硬卧 {{ ticket.yw }} 张 · <b>¥{{ ticket.ywPrice }}</b></span>
                    </div>
                    <a-button type="primary" class="select-button" @click="goToTicket(ticket)">
                      去购票
                    </a-button>
                  </article>
                </div>

                <div v-if="item.itineraries && item.itineraries.length" class="itinerary-list">
                  <article v-for="(plan, planIndex) in item.itineraries" :key="planIndex" class="itinerary-card">
                    <div class="itinerary-header">
                      <div>
                        <a-tag :color="plan.itineraryType === 'TRANSFER' ? 'orange' : 'green'">
                          {{ itineraryTypeLabel(plan.itineraryType) }}
                        </a-tag>
                        <strong>{{ formatDuration(plan.totalMinutes) }}</strong>
                        <span v-if="plan.totalPrice !== null && plan.totalPrice !== undefined">
                          约 ¥{{ plan.totalPrice }}
                        </span>
                      </div>
                      <small>{{ plan.recommendation }}</small>
                    </div>
                    <div class="itinerary-legs">
                      <div v-for="(leg, legIndex) in plan.legs" :key="`${leg.trainCode}-${legIndex}`" class="itinerary-leg">
                        <div class="leg-code">{{ leg.trainCode }}</div>
                        <div>
                          <strong>{{ formatTime(leg.startTime) }}</strong>
                          <span>{{ leg.start }}</span>
                        </div>
                        <div class="leg-arrow">→</div>
                        <div>
                          <strong>{{ formatTime(leg.endTime) }}</strong>
                          <span>{{ leg.end }}</span>
                        </div>
                        <a-button size="small" @click="goToTicket(leg)">购买此程</a-button>
                      </div>
                      <div v-if="plan.transferStation" class="transfer-hint">
                        在 {{ plan.transferStation }} 换乘 · 预留 {{ plan.transferMinutes }} 分钟
                      </div>
                    </div>
                  </article>
                </div>
                <time>{{ item.time }}</time>
              </div>
              <div v-if="item.role === 'user'" class="user-avatar"><user-outlined /></div>
            </div>
          </template>

          <div v-if="sending" class="message-row assistant">
            <div class="bot-avatar"><robot-outlined /></div>
            <div class="message-bubble thinking">
              <i></i><i></i><i></i>
              <span>正在理解你的行程需求…</span>
            </div>
          </div>
          <div ref="messageEndRef" class="message-end-anchor"></div>
        </div>

        <div class="composer">
          <div class="composer-box">
            <textarea
                v-model="input"
                :disabled="sending"
                rows="1"
                maxlength="2000"
                placeholder="例如：帮我查明天下午从上海到南京的二等座，最晚九点到"
                @keydown.enter.exact.prevent="sendMessage"
                @keydown.enter.shift.exact.stop
            ></textarea>
            <button :disabled="!input.trim() || sending" class="send-button" @click="sendMessage">
              <loading-outlined v-if="sending" />
              <arrow-up-outlined v-else />
            </button>
          </div>
          <p>Enter 发送 · Shift + Enter 换行 · AI 推荐仅供参考，请以实时余票为准</p>
        </div>
      </section>

      <aside class="info-panel">
        <div class="info-card accent-card">
          <div class="info-icon"><bulb-outlined /></div>
          <h3>描述越具体，推荐越准确</h3>
          <p>建议包含日期、出发站、到达站、时间范围、座席和预算。</p>
        </div>
        <div class="info-card">
          <h3>我能帮你</h3>
          <ul>
            <li><check-circle-filled /> 理解自然语言行程需求</li>
            <li><check-circle-filled /> 自动补充缺失查询条件</li>
            <li><check-circle-filled /> 筛选时间、座席和价格</li>
            <li><check-circle-filled /> 查询系统实时车次余票</li>
          </ul>
        </div>
        <div class="info-card privacy-card">
          <safety-certificate-outlined />
          <div>
            <strong>安全提示</strong>
            <p>当前助手只执行查询，不会自动提交订单或修改个人信息。</p>
          </div>
        </div>
      </aside>
    </div>

  </div>
</template>

<script>
import {computed, defineComponent, nextTick, onMounted, ref} from "vue";
import axios from "axios";
import {notification} from "ant-design-vue";
import router from "@/router";

const SEAT_LABELS = {
  YDZ: "一等座",
  EDZ: "二等座",
  RW: "软卧",
  YW: "硬卧"
};

const CONVERSATION_STORAGE_KEY = "trainmind_conversation_id";

export default defineComponent({
  name: "assistant-view",
  setup() {
    const input = ref("");
    const sending = ref(false);
    const conversationId = ref(localStorage.getItem(CONVERSATION_STORAGE_KEY));
    const messages = ref([]);
    const messageEndRef = ref(null);
    const starters = [
      {
        title: "按时间查票",
        description: "筛选最晚到达时间",
        prompt: "帮我查明天下午从上海到南京的二等座，最晚晚上九点到",
        icon: "ClockCircleOutlined"
      },
      {
        title: "按预算推荐",
        description: "控制座席和价格范围",
        prompt: "我想从北京去济南，预算300元以内，优先二等座",
        icon: "PayCircleOutlined"
      },
      {
        title: "周末出行",
        description: "规划周末短途行程",
        prompt: "帮我看看这周六从杭州到上海的车票",
        icon: "CompassOutlined"
      }
    ];

    const shortConversationId = computed(() =>
      conversationId.value ? conversationId.value.slice(0, 8) : ""
    );

    const now = () => new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit"
    });

    const scrollToBottom = async (smooth = true) => {
      await nextTick();
      await new Promise(resolve => requestAnimationFrame(resolve));
      messageEndRef.value?.scrollIntoView({
        behavior: smooth ? "smooth" : "auto",
        block: "end"
      });
    };

    const restoreConversation = async () => {
      if (!conversationId.value) return;
      try {
        const response = await axios.get(
          `/agent/api/v1/conversations/${conversationId.value}`
        );
        messages.value = (response.data.messages || []).map((item, index) => ({
          ...item,
          id: `restored-${index}`,
          time: item.time
            ? new Date(item.time).toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit"
            })
            : ""
        }));
        await scrollToBottom(false);
      } catch (error) {
        if (error.response?.status === 404) {
          conversationId.value = null;
          localStorage.removeItem(CONVERSATION_STORAGE_KEY);
        }
      }
    };

    onMounted(restoreConversation);

    const sendMessage = async () => {
      const content = input.value.trim();
      if (!content || sending.value) return;

      messages.value.push({id: Date.now(), role: "user", content, time: now()});
      input.value = "";
      sending.value = true;
      await scrollToBottom();

      try {
        const response = await axios.post("/agent/api/v1/chat", {
          conversationId: conversationId.value,
          message: content
        });
        const data = response.data;
        conversationId.value = data.conversationId;
        localStorage.setItem(CONVERSATION_STORAGE_KEY, data.conversationId);
        messages.value.push({
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: data.message,
          constraints: data.constraints,
          tickets: data.tickets || [],
          itineraries: data.itineraries || [],
          time: now()
        });
      } catch (error) {
        const status = error.response?.status;
        const detail = error.response?.data?.message || error.response?.data?.error;
        const message = detail
          || (status ? `智能助手请求失败（HTTP ${status}）` : "智能助手暂时无法连接，请确认 Agent 和票务服务已启动。");
        messages.value.push({
          id: `${Date.now()}-error`,
          role: "assistant",
          content: message,
          time: now()
        });
        notification.error({description: message});
      } finally {
        sending.value = false;
        await scrollToBottom();
      }
    };

    const useStarter = (prompt) => {
      input.value = prompt;
      sendMessage();
    };

    const resetConversation = () => {
      conversationId.value = null;
      localStorage.removeItem(CONVERSATION_STORAGE_KEY);
      messages.value = [];
      input.value = "";
    };

    const seatLabel = (constraints) =>
      (constraints?.seatTypes || []).map(item => SEAT_LABELS[item] || item).join("、");

    const formatTime = (value) => value ? value.slice(0, 5) : "--:--";
    const formatDuration = (minutes) => {
      const hours = Math.floor(Number(minutes) / 60);
      const rest = Number(minutes) % 60;
      return hours ? `${hours}小时${rest ? `${rest}分` : ""}` : `${rest}分钟`;
    };
    const itineraryTypeLabel = (type) => ({
      DIRECT: "直达",
      TRANSFER: "一次中转",
      ALTERNATIVE_DATE: "替代日期",
      ALTERNATIVE_STATION: "替代车站"
    }[type] || type);
    const available = (count) => Number(count) > 0;

    const goToTicket = (ticket) => {
      SessionStorage.set(SESSION_TICKET_PARAMS, {
        date: ticket.date,
        start: ticket.start,
        end: ticket.end,
        trainCode: ticket.trainCode
      });
      router.push("/ticket");
    };

    return {
      input,
      sending,
      conversationId,
      shortConversationId,
      messages,
      messageEndRef,
      starters,
      sendMessage,
      useStarter,
      resetConversation,
      seatLabel,
      formatTime,
      formatDuration,
      itineraryTypeLabel,
      available,
      goToTicket
    };
  }
});
</script>

<style scoped>
.assistant-page {
  min-height: calc(100vh - 136px);
  margin: -24px;
  padding: 30px;
  color: #17233d;
  text-align: left;
  background:
      radial-gradient(circle at 82% 4%, rgba(56, 189, 248, .13), transparent 24%),
      linear-gradient(145deg, #f7fbff 0%, #f4f7fb 52%, #eef7f5 100%);
}

.assistant-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  max-width: 1280px;
  margin: 0 auto 22px;
}

.eyebrow {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 7px;
  color: #168a75;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.eyebrow span {
  width: 20px;
  height: 2px;
  background: #20a78d;
}

.assistant-hero h1 {
  margin: 0;
  color: #14213d;
  font-size: 32px;
  line-height: 1.25;
  letter-spacing: -.02em;
}

.assistant-hero p {
  margin: 8px 0 0;
  color: #718096;
  font-size: 15px;
}

.hero-status {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 14px;
  padding: 8px 13px;
  color: #337768;
  border: 1px solid #d8eee8;
  border-radius: 999px;
  background: rgba(255,255,255,.78);
  font-size: 12px;
  font-weight: 600;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34,197,94,.12);
}

.assistant-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  max-width: 1280px;
  margin: 0 auto;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 220px);
  min-height: 620px;
  max-height: 800px;
  overflow: hidden;
  border: 1px solid rgba(209, 219, 232, .85);
  border-radius: 22px;
  background: rgba(255,255,255,.92);
  box-shadow: 0 20px 60px rgba(42, 67, 101, .09);
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 62px;
  padding: 0 22px;
  border-bottom: 1px solid #edf1f6;
}

.chat-toolbar strong { font-size: 15px; }
.chat-toolbar span { margin-left: 12px; color: #a0aec0; font-size: 11px; }

.message-list {
  flex: 1;
  min-height: 0;
  padding: 25px;
  overflow-y: auto;
  scroll-behavior: smooth;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.message-end-anchor {
  width: 100%;
  height: 1px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 455px;
  text-align: center;
}

.empty-state h2 { margin: 16px 0 6px; font-size: 23px; }
.empty-state > p { margin: 0 0 24px; color: #8390a4; }

.starter-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: min(720px, 100%);
}

.starter-card {
  display: grid;
  grid-template-columns: 32px 1fr 16px;
  gap: 10px;
  align-items: center;
  padding: 15px;
  color: #314158;
  text-align: left;
  border: 1px solid #e5ebf2;
  border-radius: 14px;
  background: #fbfdff;
  cursor: pointer;
  transition: .2s ease;
}

.starter-card:hover {
  border-color: #8dd5c7;
  background: #f5fffc;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(31, 140, 119, .10);
}

.starter-card > svg { color: #16977e; font-size: 20px; }
.starter-card > svg:last-child { color: #aab4c1; font-size: 12px; }
.starter-card span { display: flex; flex-direction: column; min-width: 0; }
.starter-card strong { font-size: 13px; }
.starter-card small { margin-top: 3px; color: #8b97a8; font-size: 11px; }

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 24px;
}

.message-row.user { justify-content: flex-end; }
.message-content { max-width: min(82%, 800px); }

.bot-avatar, .user-avatar {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 11px;
}

.bot-avatar {
  color: white;
  background: linear-gradient(145deg, #176c8b, #1eaa8e);
  box-shadow: 0 5px 14px rgba(30, 146, 130, .2);
}

.bot-avatar.large { width: 52px; height: 52px; border-radius: 16px; font-size: 23px; }
.user-avatar { color: #53647a; background: #e9eff6; }

.message-bubble {
  padding: 12px 15px;
  color: #334155;
  white-space: pre-wrap;
  border: 1px solid #e6ecf2;
  border-radius: 5px 15px 15px 15px;
  background: #f8fafc;
  font-size: 14px;
  line-height: 1.7;
}

.user .message-bubble {
  color: white;
  border-color: transparent;
  border-radius: 15px 5px 15px 15px;
  background: linear-gradient(135deg, #177b91, #199d85);
}

.message-content time {
  display: block;
  margin-top: 6px;
  color: #a3adbb;
  font-size: 10px;
}

.user .message-content time { text-align: right; }

.constraint-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}

.constraint-list span {
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 5px 9px;
  color: #507062;
  border: 1px solid #dceee8;
  border-radius: 999px;
  background: #f4fbf9;
  font-size: 11px;
}

.ticket-list { display: grid; gap: 9px; margin-top: 12px; }
.itinerary-list { display: grid; gap: 10px; margin-top: 12px; }
.itinerary-card { padding: 15px; border: 1px solid #dfe9e6; border-radius: 14px; background: #fbfefd; }
.itinerary-header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 12px; }
.itinerary-header > div { display: flex; gap: 10px; align-items: center; }
.itinerary-header strong { color: #173d38; }
.itinerary-header span, .itinerary-header small { color: #718096; font-size: 11px; }
.itinerary-legs { display: grid; gap: 7px; }
.itinerary-leg { display: grid; grid-template-columns: 70px 1fr 20px 1fr 76px; gap: 10px; align-items: center; padding: 10px; border-radius: 10px; background: white; }
.itinerary-leg > div:not(.leg-code):not(.leg-arrow) { display: flex; flex-direction: column; }
.itinerary-leg span { color: #7a8798; font-size: 11px; }
.leg-code { color: #176f65; font-weight: 700; }
.leg-arrow { color: #91a7a1; }
.transfer-hint { padding: 6px 10px; color: #b26a2d; border-radius: 8px; background: #fff7ed; font-size: 11px; text-align: center; }
.ticket-card {
  display: grid;
  grid-template-columns: 120px minmax(240px, 1fr) minmax(160px, auto) 88px;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border: 1px solid #e4eaf1;
  border-radius: 14px;
  background: white;
  box-shadow: 0 5px 18px rgba(42, 67, 101, .05);
}

.train-code { display: flex; flex-direction: column; }
.train-code > span { color: #183b57; font-size: 21px; font-weight: 800; }
.train-code small { margin-top: 4px; color: #16947c; font-size: 10px; }
.journey-time { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; }
.journey-time > div:not(.journey-line) { display: flex; flex-direction: column; }
.journey-time strong { font-size: 18px; }
.journey-time span { margin-top: 2px; color: #738197; font-size: 11px; }
.journey-line { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; position: relative; color: #6cae9f; }
.journey-line span { height: 1px; margin: 0; background: #bddbd4; }
.journey-line small { position: absolute; top: 13px; left: 50%; color: #9aa5b3; font-size: 9px; transform: translateX(-50%); }
.seat-summary { display: flex; flex-direction: column; gap: 3px; color: #68778c; font-size: 11px; }
.seat-summary b { color: #e17645; }
.select-button { border-radius: 8px; background: #168e78; box-shadow: none; }

.thinking { display: flex; gap: 5px; align-items: center; color: #718096; }
.thinking i { width: 5px; height: 5px; border-radius: 50%; background: #24a88f; animation: bounce 1.1s infinite; }
.thinking i:nth-child(2) { animation-delay: .15s; }
.thinking i:nth-child(3) { animation-delay: .3s; }
.thinking span { margin-left: 5px; font-size: 12px; }
@keyframes bounce { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-5px); } }

.composer { padding: 14px 20px 16px; border-top: 1px solid #edf1f6; background: rgba(250,252,254,.9); }
.composer-box {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 9px 10px 9px 15px;
  border: 1px solid #dce4ed;
  border-radius: 15px;
  background: white;
  transition: .2s;
}
.composer-box:focus-within { border-color: #61b8a6; box-shadow: 0 0 0 3px rgba(38,166,140,.10); }
.composer textarea { flex: 1; max-height: 100px; padding: 7px 0; resize: none; outline: none; border: 0; background: transparent; font: inherit; line-height: 1.5; }
.send-button { display: grid; width: 38px; height: 38px; color: white; border: 0; border-radius: 11px; background: linear-gradient(135deg, #167f91, #18a181); place-items: center; cursor: pointer; }
.send-button:disabled { background: #cbd5df; cursor: not-allowed; }
.composer > p { margin: 7px 0 0; color: #a1abba; text-align: center; font-size: 10px; }

.info-panel { display: flex; flex-direction: column; gap: 14px; }
.info-card { padding: 20px; border: 1px solid rgba(216,225,235,.9); border-radius: 17px; background: rgba(255,255,255,.82); box-shadow: 0 10px 30px rgba(42,67,101,.05); }
.info-card h3 { margin: 0 0 10px; font-size: 14px; }
.info-card p { margin: 0; color: #7d899a; font-size: 12px; line-height: 1.7; }
.accent-card { background: linear-gradient(145deg, #ecfbf7, #f8fffd); }
.info-icon { display: grid; width: 36px; height: 36px; margin-bottom: 15px; color: #158b75; border-radius: 11px; background: #d5f3eb; place-items: center; font-size: 17px; }
.info-card ul { display: flex; flex-direction: column; gap: 12px; padding: 0; margin: 0; list-style: none; }
.info-card li { display: flex; gap: 8px; align-items: center; color: #58677a; font-size: 12px; }
.info-card li svg { color: #27ad8e; }
.privacy-card { display: flex; gap: 12px; color: #59706a; }
.privacy-card > svg { flex: 0 0 auto; color: #1a957c; font-size: 20px; }
.privacy-card strong { display: block; margin-bottom: 5px; font-size: 12px; }

@media (max-width: 1100px) {
  .assistant-layout { grid-template-columns: 1fr; }
  .info-panel { display: grid; grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 760px) {
  .assistant-page { margin: -24px; padding: 20px 12px; }
  .assistant-hero { flex-direction: column; }
  .assistant-hero h1 { font-size: 26px; }
  .starter-grid, .info-panel { grid-template-columns: 1fr; }
  .chat-panel {
    height: calc(100vh - 150px);
    min-height: 560px;
    max-height: none;
    border-radius: 16px;
  }
  .message-list { padding: 16px 12px; }
  .message-content { max-width: 88%; }
  .ticket-card { grid-template-columns: 1fr; }
  .select-button { width: 100%; }
}
</style>
