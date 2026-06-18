package com.knowledge.demo.controller;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.knowledge.demo.entity.TroubleTicket;
import com.knowledge.demo.repository.TroubleTicketRepository;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:5173")
public class ChatController {

    @Autowired
    private TroubleTicketRepository ticketRepository;

    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@RequestBody ChatRequest request) {
        SseEmitter emitter = new SseEmitter(600000L); 

        executor.execute(() -> {
            StringBuilder fullResponse = new StringBuilder();
            try {
                HttpClient client = HttpClient.newBuilder()
                        .version(HttpClient.Version.HTTP_1_1)
                        .build();
                
                String requestBody = objectMapper.writeValueAsString(request);
                
                HttpRequest pyRequest = HttpRequest.newBuilder()
                        .uri(URI.create("http://127.0.0.1:8000/api/rag"))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(requestBody, java.nio.charset.StandardCharsets.UTF_8)) 
                        .build();

                client.sendAsync(pyRequest, HttpResponse.BodyHandlers.ofInputStream())
                    .thenAccept(response -> {
                        try (BufferedReader reader = new BufferedReader(new InputStreamReader(response.body()))) {
                            String line;
                            while ((line = reader.readLine()) != null) {
                                if (line.startsWith("data:")) {
                                    String content = line.substring(5).trim();
                                    
                                    if ("[DONE]".equals(content)) {
                                        break;
                                    }
                                    
                                    fullResponse.append(content);
                                    emitter.send(SseEmitter.event().data(content));
                                }
                            }
                            
                            String finalAnswer = fullResponse.toString().trim();
                            
                            if (finalAnswer.contains("无法回答") || 
                                finalAnswer.contains("抱歉") || 
                                finalAnswer.contains("人工") ||
                                finalAnswer.contains("转人工")) {
                                
                                TroubleTicket ticket = new TroubleTicket();
                                ticket.setUserQuestion(request.getQuery());
                                ticket.setBotResponse(finalAnswer);
                                ticket.setStatus("pending");
                                ticketRepository.save(ticket);
                                
                                System.out.println("创建工单成功，ID: " + ticket.getId());
                            }
                            
                            emitter.complete();
                        } catch (Exception e) {
                            emitter.completeWithError(e);
                        }
                    });
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        });

        return emitter;
    }
}

class ChatRequest {
    private String query;
    private Integer topK = 5;
    private Boolean stream = true;
    
    public String getQuery() { return query; }
    public void setQuery(String query) { this.query = query; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public Boolean getStream() { return stream; }
    public void setStream(Boolean stream) { this.stream = stream; }
}