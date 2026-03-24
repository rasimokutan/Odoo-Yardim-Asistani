/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

class OdooHelpAssistant extends Component {
    static template = "odoo_help_assistant.ChatbotAction";
    static props = { ...standardActionServiceProps };

    setup() {
        this.notification = useService("notification");
        this.messageListRef = useRef("messageList");
        this.state = useState({
            canUseChatbot: false,
            chatbotEnabled: true,
            sessions: [],
            currentSessionId: null,
            messages: [],
            draft: "",
            loading: true,
            creatingSession: false,
            sending: false,
            error: null,
        });

        onWillStart(async () => {
            await this.loadBootstrap();
        });
    }

    get currentSession() {
        return this.state.sessions.find((item) => item.id === this.state.currentSessionId) || null;
    }

    get displayedMessages() {
        const messages = [...this.state.messages];
        if (this.state.sending) {
            messages.push({
                id: "pending-assistant",
                role: "assistant",
                content: "Yanit hazirlaniyor, lutfen bekleyin...",
                timestamp: new Date().toISOString(),
            });
        }
        return messages;
    }

    async loadBootstrap() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await rpc("/odoo_help_assistant/chat/bootstrap", {});
            this.state.canUseChatbot = data.can_use_chatbot;
            this.state.chatbotEnabled = data.chatbot_enabled;
            this.state.sessions = data.sessions || [];
            if (this.state.sessions.length) {
                await this.loadSession(this.state.sessions[0].id);
            }
        } catch (error) {
            this.handleError(error, "Sohbet verileri yuklenemedi.");
        } finally {
            this.state.loading = false;
        }
    }

    async loadSession(sessionId) {
        this.state.error = null;
        try {
            const payload = await rpc("/odoo_help_assistant/chat/session/load", { session_id: sessionId });
            this.upsertSession(payload);
            this.state.currentSessionId = payload.id;
            this.state.messages = payload.messages || [];
            this.scrollMessagesToBottom();
        } catch (error) {
            this.handleError(error, "Sohbet oturumu acilamadi.");
        }
    }

    async createSession() {
        if (!this.state.canUseChatbot) {
            this.handleError({ message: "Bu yardim asistanini kullanma yetkiniz bulunmuyor." }, "Yetki bulunamadi.");
            return;
        }
        this.state.creatingSession = true;
        this.state.error = null;
        try {
            const payload = await rpc("/odoo_help_assistant/chat/session/create", {});
            this.state.sessions = [payload, ...this.state.sessions.filter((item) => item.id !== payload.id)];
            this.state.currentSessionId = payload.id;
            this.state.messages = payload.messages || [];
            this.state.draft = "";
            this.scrollMessagesToBottom();
        } catch (error) {
            this.handleError(error, "Yeni sohbet olusturulamadi.");
        } finally {
            this.state.creatingSession = false;
        }
    }

    async onSendMessage() {
        const draft = (this.state.draft || "").trim();
        if (!draft || this.state.sending || !this.state.canUseChatbot) {
            return;
        }
        this.state.sending = true;
        this.state.error = null;
        try {
            const payload = await rpc("/odoo_help_assistant/chat/send", {
                message: draft,
                session_id: this.state.currentSessionId || false,
                user_context: {
                    active_menu: this.props.action?.name || "",
                    active_model: this.props.action?.res_model || "",
                },
            });
            this.upsertSession(payload);
            this.state.currentSessionId = payload.id;
            this.state.messages = payload.messages || [];
            this.state.draft = "";
            this.scrollMessagesToBottom();
        } catch (error) {
            this.handleError(error, "Mesaj gonderilemedi.");
        } finally {
            this.state.sending = false;
        }
    }

    async onSelectSession(sessionId) {
        if (sessionId === this.state.currentSessionId) {
            return;
        }
        await this.loadSession(sessionId);
    }

    async onSessionClick(ev) {
        const sessionId = parseInt(ev.currentTarget.dataset.sessionId, 10);
        if (sessionId) {
            await this.onSelectSession(sessionId);
        }
    }

    onDraftKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.onSendMessage();
        }
    }

    upsertSession(payload) {
        const session = {
            id: payload.id,
            name: payload.name,
            last_message_at: payload.last_message_at,
            message_count: payload.message_count,
            last_message_preview: payload.last_message_preview,
        };
        const others = this.state.sessions.filter((item) => item.id !== session.id);
        this.state.sessions = [session, ...others];
    }

    scrollMessagesToBottom() {
        setTimeout(() => {
            const el = this.messageListRef.el;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        }, 0);
    }

    formatTimestamp(value) {
        if (!value) {
            return "";
        }
        return new Intl.DateTimeFormat("tr-TR", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        }).format(new Date(value));
    }

    handleError(error, fallbackMessage) {
        const message = error?.data?.message || error?.message || fallbackMessage;
        this.state.error = message;
        this.notification.add(message, { type: "danger" });
    }
}

registry.category("actions").add("odoo_help_assistant.main", OdooHelpAssistant);
