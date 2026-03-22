# 🍕 Domino's Pizza Voice AI Receptionist

A fully working, real-time voice AI agent that acts as a phone receptionist for Domino's Pizza India. You speak into your microphone, it listens, understands, and replies through your speakers — just like talking to a real person on a phone call.

---

## What It Does

When you run the program, an AI agent named **Priya** answers the call and:

1. Greets you and asks for your name
2. Takes your pizza order — one question at a time
3. Asks for your delivery address
4. Reads the full order back to confirm
5. Offers one upsell deal (Choco Lava Cake, Garlic Bread, Pepsi, etc.)
6. Gives a 30–45 minute delivery estimate and **automatically ends the call**

Beyond ordering, Priya handles **18 call scenarios** including complaints, refunds, allergy queries, bulk orders, and more — and logs everything to a live browser dashboard in real time.

---

## Tech Stack

| Layer | Service | Detail |
|---|---|---|
| **Speech-to-Text** | Deepgram nova-3-general | Fast, accurate, free tier |
| **AI Brain** | Groq llama-3.1-8b-instant | Ultra-fast inference, free tier |
| **Text-to-Speech** | Cartesia sonic-3 | Natural voice, word-level timestamps |
| **Framework** | Pipecat | Real-time voice pipeline |
| **Dashboard** | FastAPI + WebSocket | Live browser UI at `localhost:8000` |

---

## Project Structure

```
dominos-voice-agentv2/
├── main.py           ← Pipeline setup, tool registration, call-end logic
├── tools.py          ← 5 LLM-callable tools (confirm, upsell, finalise, complaint, refund)
├── system_prompt.py  ← Priya's personality, menu, 18 scenarios, tool rules
├── ui.py             ← Pipecat FrameProcessor — drives dashboard + latency timing
├── web_ui.py         ← FastAPI + WebSocket server, order/complaint/latency tracking
├── static/
│   └── index.html    ← Jarvis-style animated browser dashboard
├── requirements.txt  ← All Python dependencies
├── .env.example      ← Template for API keys
└── .env              ← Your actual API keys (never commit this)
```

---

## How It Works — The Pipeline

```
Your Microphone
      ↓
Deepgram STT       ← converts speech to text in real time
      ↓
User Aggregator    ← waits for pause (0.3s VAD), mutes mic during tool calls
      ↓
Groq LLM           ← generates Priya's reply (may call tools mid-conversation)
      ↓
Cartesia TTS       ← token-stream mode: starts speaking before full reply is ready
      ↓
Your Speakers
      ↓
Assistant Aggregator  ← stores reply in conversation memory
      ↓
UI Observer           ← measures latency, drives live browser dashboard
```

**Latency optimisations applied:**
- `TextAggregationMode.TOKEN` — TTS starts on the first token, not after a full sentence
- `llama-3.1-8b-instant` — 4–5× faster than 70B on Groq's free tier
- VAD `stop_secs=0.3` — speech-end detection 40% faster than default
- Word-level `TTSTextFrame` timestamps — chat text stays in sync with audio

---

## The Five AI Tools (Function Calling)

The LLM can call these Python functions mid-conversation. Each one updates the live dashboard instantly.

### `confirm_order`
Called when the customer confirms their full order and address.
- Logs customer name, items, delivery address, total
- Updates the **Order Cart** panel on the dashboard
- Tells the LLM: "Order logged, ask one upsell question"

### `add_upsell_item`
Called when the customer accepts an upsell offer.
- Appends the upsell item and price to the Order Cart
- Tells the LLM: "Item added, say the closing line"

### `finalise_order`
Called at the very end after the closing line.
- Marks order as finalised with delivery ETA
- **Automatically shuts down the pipeline** after 3 seconds

### `log_complaint`
Called immediately when a customer reports a problem (food poisoning, wrong order, cold food, missing delivery, bad quality, late delivery).
- Logs complaint type, customer name, and full complaint text
- Pushes a red-bordered complaint event to the dashboard
- Increments the complaints counter in the stats bar

### `initiate_refund`
Called when a monetary refund is promised.
- Logs refund amount and reason
- Pushes a purple-bordered refund event to the dashboard

---

## The 18 Call Scenarios

Priya is trained to handle any of these situations naturally:

| # | Scenario | Trigger |
|---|---|---|
| 1 | Food Poisoning | Customer reports falling sick after eating |
| 2 | Wrong Order | Received wrong pizza / toppings |
| 3 | Missing Delivery | Order placed but never arrived |
| 4 | Late Delivery | Order taking more than 45 minutes |
| 5 | Cold / Bad Quality | Food arrived cold, stale, or undercooked |
| 6 | Allergy Concern | Gluten, dairy, nuts, egg questions |
| 7 | Jain / Vegan Diet | No onion/garlic or strict veg requests |
| 8 | Bulk / Party Order | 5+ pizzas for an event |
| 9 | Track Existing Order | Where is my order? |
| 10 | Modify Order | Change order after placing |
| 11 | Refund Request | Money back for cancelled/bad order |
| 12 | Store Hours / Location | Timings and nearest store |
| 13 | Offers / Discounts | Deals, coupons, loyalty points |
| 14 | Angry Customer | Shouting or abusive caller |
| 15 | Is Priya a Robot? | "Am I talking to AI?" |
| 16 | Cancel Order | Cancel a placed order |
| 17 | Prank Call | Joking or off-topic caller |
| 18 | Outside Delivery Zone | Address not serviceable |

---

## The Browser Dashboard

When running, your browser opens at **`http://localhost:8000`** and shows:

### Status Panel (left)
- Animated orb: IDLE / LISTENING / THINKING / SPEAKING
- Waveform bars and radial equalizer (canvas-animated)
- Signal strength meter with live jitter
- **Latency meter** — measures ms from end of your speech to start of Priya's audio
- **Turn counter** — total conversation turns
- **Active scenario tag** — lights up when a scenario is detected
- All 18 scenario chips (the active one highlights)

### Conversation Panel (centre)
- Live chat transcript — your messages and Priya's replies
- Text appears word-by-word in sync with the audio (Cartesia word timestamps)
- Recording indicator while you speak, typing dots while Priya thinks

### Right Column
- **Order Cart** (top) — customer name, delivery address, itemised order, upsell add-ons, grand total, status badge, ETA
- **Event Log** (bottom) — all tool-call events colour-coded:
  - 🟢 Green — order confirmed
  - 🟡 Yellow — upsell added
  - 🔵 Cyan — order finalised
  - 🔴 Red — complaint logged
  - 🟣 Purple — refund initiated

### Stats Bar (top)
Calls · Orders · Revenue · Upsells · **Complaints** · **Avg Latency** · Duration

### Flow Bar
Visual pipeline showing: GREETING → ORDERING → CONFIRMED → UPSELL → COMPLETE

---

## Setup (First Time)

### Step 1 — Get Free API Keys

| Service | Link | Notes |
|---|---|---|
| Deepgram | https://console.deepgram.com | Sign up → copy API Key |
| Groq | https://console.groq.com/keys | Sign up → Create API key |
| Cartesia | https://play.cartesia.ai | Sign up → Settings → API Keys |

### Step 2 — Install Python 3.12

Download from: https://python.org/downloads/release/python-3120
**Important:** Check "Add Python to PATH" during install.

### Step 3 — Clone and set up the project

```powershell
git clone https://github.com/sahil00000001/dominos-voice-agentv2.git
cd dominos-voice-agentv2

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Step 4 — Add Your API Keys

```powershell
copy .env.example .env
notepad .env
```

Fill in your three keys:

```env
DEEPGRAM_API_KEY=dg_xxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
CARTESIA_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Running the Agent

```powershell
# Activate the virtual environment (only needed once per terminal session)
.\.venv\Scripts\Activate.ps1

# Run the agent
python main.py
```

The browser dashboard opens automatically at **http://localhost:8000**.
Speak into your microphone. Press **Ctrl+C** to end the session.

> **Tip:** Use **headphones** for the best experience. Without headphones, the microphone can pick up Priya's voice from the speakers and create an echo loop.

---

## Every Time You Come Back

```powershell
cd dominos-voice-agentv2
.\.venv\Scripts\Activate.ps1
python main.py
```

---

## Menu

| Pizza | Regular | Medium | Large |
|---|---|---|---|
| Margherita | ₹199 | ₹299 | ₹499 |
| Farmhouse | ₹249 | ₹349 | ₹549 |
| Veggie Paradise | ₹249 | ₹349 | ₹549 |
| Paneer Makhani | ₹279 | ₹379 | ₹599 |
| Double Cheese Margherita | ₹229 | ₹329 | ₹529 |
| Chicken Dominator | ₹299 | ₹399 | ₹649 |
| Pepper Barbeque Chicken | ₹279 | ₹379 | ₹599 |
| Chicken Golden Delight | ₹269 | ₹369 | ₹579 |
| Keema Do Pyaza | ₹299 | ₹399 | ₹649 |

**Sides & Drinks (upsell):** Garlic Bread ₹79 · Choco Lava Cake ₹49 · Pepsi ₹30

---

## Customisation

- **Change Priya's voice** — Browse voices at https://play.cartesia.ai and replace `voice_id` in `main.py`
- **Change the menu** — Edit `system_prompt.py`
- **Change the personality** — Edit the call flow rules in `system_prompt.py`
- **Add more tools** — Add a handler in `tools.py`, register it in `main.py`, add a schema in `get_tool_definitions()`
- **Connect to a real POS** — Replace the log calls in `tools.py` with actual API calls to your ordering system

---

## Dependencies

```
pipecat-ai[cartesia,deepgram,groq,local]  ← core framework + all services
torch (CPU)                                ← powers the Silero VAD model
python-dotenv                              ← loads API keys from .env
fastapi + uvicorn                          ← web dashboard server
```

---

*Built with Pipecat · Groq llama-3.1-8b-instant · Deepgram nova-3 · Cartesia sonic-3*
