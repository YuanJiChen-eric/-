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

import com.knowledge.demo.entity.TroubleTicket;
import com.knowledge.demo.repository.TroubleTicketRepository;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class ChatController {

    @Autowired
    private TroubleTicketRepository ticketRepository;

    private final ExecutorService executor = Executors.newCachedThreadPool();

    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@RequestBody ChatRequest request) {
        // 创建一个 SseEmitter，超时时间设为 10 分钟
        SseEmitter emitter = new SseEmitter(600000L); 

        executor.execute(() -> {
            StringBuilder fullResponse = new StringBuilder();
            try {
                // 1. 调用成员 A 部署的 Python 接口（假设它运行在本地 8000 端口）
                HttpClient client = HttpClient.newHttpClient();
                String requestBody = "{\"query\": \"" + request.getQuery() + "\"}";
                
                HttpRequest pyRequest = HttpRequest.newBuilder()
                        .uri(URI.create("http://localhost:8000/api/rag")) // 成员 A 提供的 API 地址
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                        .build();

                // 2. 以流的方式读取 Python 端返回的响应
                client.sendAsync(pyRequest, HttpResponse.BodyHandlers.ofInputStream())
                    .thenAccept(response -> {
                        try (BufferedReader reader = new BufferedReader(new InputStreamReader(response.body()))) {
                            String line;
                            while ((line = reader.readLine()) != null) {
                                if (line.startsWith("data:")) {
                                    String content = line.substring(5).trim();
                                    fullResponse.append(content);
                                    // 3. 将大模型的每一个字（Chunk）转发给前端
                                    emitter.send(SseEmitter.event().data(content));
                                }
                            }
                            
                            // 4. 判断是否需要触发“转人工”逻辑
                            String finalAns = fullResponse.toString();
                            if (finalAns.contains("无法回答") || finalAns.contains("抱歉") || finalAns.contains("人工")) {
                                // 自动创建一张工单
                                TroubleTicket ticket = new TroubleTicket();
                                ticket.setUserQuestion(request.getQuery());
                                ticket.setBotResponse(finalAns);
                                ticket.setStatus("pending");
                                ticketRepository.save(ticket);
                                
                                // 发送特殊指令告诉前端：此问题已转人工，前端应展示“转人工提示”
                                emitter.send(SseEmitter.event().name("system").data("{\"action\":\"transfer_to_human\",\"ticket_id\":" + ticket.getId() + "}"));
                            }
                            
                            emitter.complete(); // 传输完成
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

// 简单的请求封装类
class ChatRequest {
    private String query;
    public String getQuery() { return query; }
    public void setQuery(String query) { this.query = query; }
}