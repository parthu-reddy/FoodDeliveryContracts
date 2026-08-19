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
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "CHAT_MESSAGE_SENT",
            payload: [
                chatId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                senderId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                message: "Where is my food?"
            ]
        ])
    }
}
