# 🤖 WhatsApp AI Auto Reply Bot

An advanced **AI-powered WhatsApp automation tool** that reads incoming messages and replies automatically using a local AI model.

Built with **Python + Selenium + Ollama + CustomTkinter**, this bot acts like your personal assistant—replying instantly, intelligently, and privately.

---

## 🚀 Features

* 📥 Detects unread WhatsApp messages automatically
* 🧠 Generates smart replies using local AI (Ollama)
* 📤 Sends responses like a real user
* 🖥️ Modern GUI built with CustomTkinter
* ⚙️ Custom system prompt for AI behavior
* 🔄 Real-time message monitoring
* 📊 Live logs & message counter
* 🧪 Headless mode support
* 🔒 Fully local (no paid APIs required)

---

## 🖼️ Preview

> Clean UI with live logs, status indicator, and control panel.

---

## 🧠 Tech Stack

* **Python**
* **Selenium** (Browser automation)
* **Ollama** (Local LLM)
* **CustomTkinter** (Modern GUI)
* **Requests** (API communication)

---

## 📁 Project Structure

```bash
.
├── app.py          # GUI Application
├── bot_logic.py    # Core automation & AI logic
└── README.md
```

---

## ⚙️ Requirements

* Python 3.9+
* Google Chrome
* ChromeDriver (matching your Chrome version)
* Ollama installed

---

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/whatsapp-ai-bot.git
cd whatsapp-ai-bot
```

---

### 2. Install Dependencies

```bash
pip install selenium customtkinter requests
```

---

### 3. Install & Run Ollama

Download from: [https://ollama.com](https://ollama.com)

Then run:

```bash
ollama serve
ollama run llama3
```

---

### 4. Run the Application

```bash
python app.py
```

---

### 5. Setup WhatsApp

* A Chrome window will open
* Scan the QR code using your phone
* The bot will start monitoring messages

---

## 🧩 Configuration

Inside the app UI:

* **Chrome Profile Path** → Save login session
* **Model** → Choose AI model (e.g., `llama3`, `phi3`)
* **Headless Mode** → Run browser in background
* **System Prompt** → Customize AI behavior

Example prompt:

```txt
Reply in 1-2 sentences max.
Do not greet unnecessarily.
Answer directly.
```

---

## ⚠️ Important Notes

* Works only with **WhatsApp Web**
* Keep **Ollama running** (`ollama serve`)
* Internet required for WhatsApp (AI runs locally)
* Avoid spamming to prevent account restrictions

---

## 🧪 Future Improvements

* 🎤 Voice message replies
* 📱 Mobile app integration
* 🧠 Context-aware memory
* 🌐 Multi-platform automation
* 🏠 Smart assistant (Jarvis-style)

---

## 🤝 Contributing

Contributions are welcome!

* Fork the repo
* Create a feature branch
* Submit a pull request

---

## 📜 License

This project is open-source and available under the **MIT License**.

---

## ❤️ Support

If you like this project:

* ⭐ Star the repo
* 🧠 Share ideas & improvements
* 🚀 Build something awesome with it

---

## 💡 Inspiration

Built as a step toward creating a real-life **AI assistant (Jarvis)** that can automate everyday tasks seamlessly.

---

**Made with passion, automation, and a bit of AI magic. ✨**
