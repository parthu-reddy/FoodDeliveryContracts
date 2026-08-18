package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send chat-events events")
    label("chat_events")
    input {
        triggeredBy('fireChatEvent()')
    }
    outputMessage {
        sentTo('chat-events')
        body([
            eventId: "chat-444",
            type: "CHAT_MESSAGE_SENT",
            payload: [
                chatId: "chat-100",
                senderId: "user-123",
                message: "Where is my food?"
            ]
        ])
    }
}
