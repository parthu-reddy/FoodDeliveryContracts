# Out of Scope for Consumer-Driven Contracts (CDC)

After an exhaustive protocol sweep across all 16 microservices (checking for `@FeignClient`, `RestTemplate`, `WebClient`, `HttpClient`, `convertAndSend`, `MessageListener`, `@GrpcClient`, `RabbitTemplate`, and `JmsTemplate`), the following mechanisms were identified and deliberately excluded from the CDC testing plan:

## 1. Frontend-Facing APIs (WebSockets & SSE)
- **STOMP WebSockets**: Found in `CommunicationService` for real-time chat.
- **Server-Sent Events (SSE)**: Found in `DeliveryExecutiveApplication` for streaming real-time driver coordinates to the customer application.
- **Why Excluded**: CDC ensures that backend microservices do not break *each other*. These frontend-facing endpoints are consumed by mobile (iOS/Android) and Web apps. They should be protected via **OpenAPI specifications and Zod validation schemas** on the client side, rather than backend-focused CDC tests.

## 2. External Third-Party APIs
- **Payment Gateways**: `CashfreeStrategy` and `VyaparGatewayStrategy` inside `PaymentGatewayIntegration` (using `WebClient`).
- **Communication Gateways**: `TwilioSmsService`, `ExotelSmsService`, `BrevoEmailService`, and `GupshupWhatsAppService` inside `CommunicationIntegration` (using `WebClient`).
- **ONDC BPP Integrations**: External API calls to BPP (Buyer Protocol Providers) from `ONDCIntegrationService` (using `RestTemplate`).
- **Why Excluded**: We cannot enforce Spring Cloud Contracts on external third-party companies. These external integrations must remain tested purely through traditional **WireMock stubs** maintained internally by the owning microservice.

## 3. Infrastructure Tooling
- **ConfigService**: Microservices fetching properties from the centralized configuration server.
- **EurekaServer**: Service discovery interactions.
- **Why Excluded**: These are underlying Spring Cloud framework interactions, not business-level APIs. Testing them is unnecessary overhead.
