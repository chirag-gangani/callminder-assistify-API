const voiceDetectionWorkletCode = `
class VoiceDetectionProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.lastVoiceDetection = 0;
    this.voiceDetectionThreshold = -35; // dB
    this.debounceTime = 300; // ms
  }

  calculateDB(input) {
    let sum = 0;
    for (let i = 0; i < input.length; i++) {
      sum += input[i] * input[i];
    }
    const rms = Math.sqrt(sum / input.length);
    return 20 * Math.log10(rms);
  }

  process(inputs) {
    const input = inputs[0][0];
    if (!input) return true;

    const currentDB = this.calculateDB(input);
    const currentTime = currentTime();

    if (currentDB > this.voiceDetectionThreshold && 
        currentTime - this.lastVoiceDetection > this.debounceTime) {
      this.lastVoiceDetection = currentTime;
      this.port.postMessage({ userSpeaking: true });
    }

    return true;
  }
}

registerProcessor('voice-detection-processor', VoiceDetectionProcessor);
`;

class VoiceChatApp {
  constructor() {
    this.ws = null;
    this.currentAudio = null;
    this.isAgentSpeaking = false;

    this.recordButton = document.getElementById("recordButton");
    this.status = document.getElementById("status");
    this.conversation = document.getElementById("conversation");
    this.makeOutboundCallButton = document.getElementById("makeOutboundCall");

    // Disable outbound call button by default
    if (this.makeOutboundCallButton) {
      this.makeOutboundCallButton.disabled = false;
    }

    // Enable recording by default
    if (this.recordButton) {
      this.recordButton.disabled = false;
      this.status.textContent = 'Click "Start Recording" to begin conversation';
    }

    this.setupFileUpload();
    this.setupEventListeners();

    // Initialize WebSocket connection immediately
    this.initializeWebSocket();

    if (this.makeOutboundCallButton) {
      this.makeOutboundCallButton.addEventListener("click", () => {
        this.makeOutboundCall();
      });
    }
  }

  setupFileUpload() {
    const fileUpload = document.getElementById("fileUpload");
    const pdfInput = document.getElementById("pdfInput");

    if (!fileUpload || !pdfInput) {
      console.log(
        "File upload elements not found - continuing without file upload functionality"
      );
      return;
    }

    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      fileUpload.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    ["dragenter", "dragover"].forEach((eventName) => {
      fileUpload.addEventListener(eventName, () => {
        fileUpload.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      fileUpload.addEventListener(eventName, () => {
        fileUpload.classList.remove("dragover");
      });
    });

    fileUpload.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files[0];
      if (file) this.handleFileUpload(file);
    });

    pdfInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) this.handleFileUpload(file);
    });
  }

  async handleFileUpload(file) {
    if (file.type !== "application/pdf") {
      this.updateUploadStatus("Please upload a PDF file", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/upload_knowledge", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (result.status === "success") {
        this.updateUploadStatus(
          "Knowledge base updated successfully✅!",
          "success"
        );
        // Enable both record and outbound call buttons
        if (this.recordButton) {
          this.recordButton.disabled = false;
        }
        if (this.makeOutboundCallButton) {
          this.makeOutboundCallButton.disabled = false;
        }
        // Reinitialize WebSocket to use new knowledge base
        this.initializeWebSocket();
      } else {
        this.updateUploadStatus(result.message || "Upload failed", "error");
      }
    } catch (error) {
      this.updateUploadStatus("Failed to upload knowledge base", "error");
    }
  }

  updateUploadStatus(message, type) {
    const uploadStatus = document.getElementById("uploadStatus");
    if (uploadStatus) {
      uploadStatus.textContent = message;
      uploadStatus.className = `upload-status ${type}`;
    }
  }

  initializeWebSocket() {
    if (this.ws) {
      this.ws.close();
    }

    this.ws = new WebSocket("ws://127.0.0.1:8000/ws");

    this.ws.onopen = () => {
      console.log("WebSocket connection established");
    };

    this.ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "ai_response") {
        this.addMessage(data.text, "agent");

        if (data.end_call) {
          if (this.ws) {
            this.ws.close();
          }
        }
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      if (this.status) {
        this.status.textContent = "Connection error. Please refresh the page.";
      }
    };

    this.ws.onclose = () => {
      console.log("WebSocket connection closed");
    };
  }

  stopCurrentAudio() {
    if (this.currentAudio) {
      this.isAgentSpeaking = false;
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
  }

  addMessage(text, sender) {
    if (!this.conversation) return;

    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${sender}-message`;
    messageDiv.textContent = text;
    this.conversation.appendChild(messageDiv);
    messageDiv.scrollIntoView({ behavior: "smooth" });
  }

  setupEventListeners() {
    if (this.recordButton) {
      this.recordButton.addEventListener("click", () => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(
            JSON.stringify({
              action: "start_recording",
            })
          );
        }
      });
    }
  }

  async makeOutboundCall() {
    try {
      const phoneNumber = prompt(
        "Enter phone number to call (include country code):"
      );
      if (!phoneNumber) return;

      const response = await fetch("/make_call", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ phone_number: phoneNumber }),
      });

      const result = await response.json();
      if (result.status === "success") {
        alert("Call initiated successfully!");
      } else {
        alert("Failed to initiate call: " + result.message);
      }
    } catch (error) {
      alert("Failed to initiate call. Please try again.");
    }
  }
}

// Initialize the app when the page loads
document.addEventListener("DOMContentLoaded", () => {
  new VoiceChatApp();
});