# GigNav Demo Script (3 minutes)

## SETUP BEFORE RECORDING
- Open these tabs:
  1. http://localhost:8080 (Voice UI)
  2. http://localhost:8080/earnings (Earnings Dashboard)
  3. http://localhost:8080/form (Complaint Form)
  4. http://localhost:8000 (ADK Multi-Agent UI - select "orchestrator")
  5. architecture.html (open in browser)

---

## 0:00 - 0:30 | THE PROBLEM (Show earnings dashboard)
**[Show Tab 2: Earnings Dashboard]**

VOICEOVER:
"Over 73,000 delivery workers in New York City rely on apps like UberEats and DoorDash for their income. But many are being paid below the city's legal minimum of $22.13 per hour. This worker, Carlos, worked 40 hours in the Bronx and only earned $14.20 an hour — that's $7.93 below the legal minimum. Filing a wage complaint takes time these workers don't have. That's why we built GigNav."

---

## 0:30 - 0:50 | THE ARCHITECTURE
**[Show Tab 5: Architecture Diagram]**

VOICEOVER:
"GigNav is a multi-agent system built on Google Cloud. An Orchestrator Agent coordinates two specialized sub-agents using Google's A2A protocol. The Data Agent queries real DCWP delivery worker data in BigQuery. The Navigator Agent uses Gemini's Computer Use API to physically control a browser. And the entire system supports voice interaction through the Gemini Live API with speech-to-text and text-to-speech."

---

## 0:50 - 2:00 | THE DEMO
**[Show Tab 4: ADK Web UI]**

1. Select "orchestrator" from the agent dropdown
2. Type: "I worked 40 hours in the Bronx this week. My base pay was $412 and I got $156 in tips."
3. Watch the orchestrator delegate to the Data Agent
4. Show the response with UNDERPAID status

VOICEOVER:
"Watch as I tell GigNav about a worker's earnings. The orchestrator recognizes this is a data query and delegates to the Data Agent via A2A protocol. The Data Agent queries BigQuery — returning that this worker is underpaid by $473.20."

**[Show Tab 1: Voice UI]**

5. Click the microphone button
6. Say: "I need help filing a wage complaint for the Bronx"
7. Show the STT transcription
8. Show the agent response

VOICEOVER:
"Workers can also speak to GigNav. Speech-to-text captures their words, the agent analyzes their situation, and text-to-speech reads the response back."

---

## 2:00 - 2:30 | COMPUTER USE
**[Show Tab 2: Earnings Dashboard, then Tab 3: Form]**

VOICEOVER:
"The most powerful feature is Computer Use. GigNav's Navigator Agent can see a worker's earnings screen, extract the data, then physically navigate to the NYC DCWP complaint form and auto-fill every field — name, hours, pay, borough, and a detailed complaint description. The worker doesn't have to fill out a single field."

**[If you have the screen recording from earlier, show it here]**
**[Otherwise, show the completed mock form with fields filled in]**

---

## 2:30 - 3:00 | TECH STACK & IMPACT
**[Show Tab 5: Architecture Diagram again]**

VOICEOVER:
"GigNav uses Gemini 3 Flash for Computer Use, Gemini 2.5 Flash for conversation, Google ADK with A2A protocol for multi-agent coordination, BigQuery for real DCWP data covering 73,000 workers, and the Gemini Live API for voice. Everything runs on Google Cloud.

Our goal is simple: automate the fight against wage theft so delivery workers can focus on earning — not paperwork. Thank you."

---

## KEY THINGS TO SHOW ON SCREEN:
- [ ] Voice UI with microphone working (STT visualization)
- [ ] ADK multi-agent delegation (orchestrator → data_agent)
- [ ] Earnings dashboard (the underpayment numbers)
- [ ] Complaint form (filled fields)
- [ ] Architecture diagram
- [ ] BigQuery data (if time - show console.cloud.google.com)
