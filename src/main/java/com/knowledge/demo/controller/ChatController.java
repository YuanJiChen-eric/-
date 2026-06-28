package com.knowledge.demo.controller;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.springframework.beans.factory.annotation.Autowired;
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

    @PostMapping(value = "/chat", produces = "text/event-stream;charset=UTF-8")
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
                        .uri(URI.create("http://127.0.0.1:8001/api/rag"))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
                        .build();

                client.sendAsync(pyRequest, HttpResponse.BodyHandlers.ofInputStream())
                    .thenAccept(response -> {
                        try (BufferedReader reader = new BufferedReader(
                                new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
                            String line;
                            while ((line = reader.readLine()) != null) {
                                if (line.startsWith("data:")) {
                                    String content = line.substring(5);
                                    if (content.startsWith(" ")) {
                                        content = content.substring(1);
                                    }

                                    if ("[DONE]".equals(content)) {
                                        break;
                                    }

                                    if (!fullResponse.isEmpty()) {
                                        fullResponse.append("\n");
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
                                
                                // 💡 核心升级：拉取所有 pending（待处理）工单，进行模糊相似度对比
                                List<TroubleTicket> pendingTickets = ticketRepository.findByStatus("pending");
                                boolean isDuplicate = false;
                                double maxSim = 0.0;
                                Long duplicateId = null;

                                for (TroubleTicket pending : pendingTickets) {
                                    double sim = getSimilarity(pending.getUserQuestion(), request.getQuery());
                                    if (sim > maxSim) {
                                        maxSim = sim;
                                        duplicateId = pending.getId();
                                    }
                                }

                                // 如果最相似的工单相似度 > 0.70 (70%)，判定为重复工单并拦截
                                if (maxSim > 0.70) {
                                    isDuplicate = true;
                                }

                                if (!isDuplicate) {
                                    TroubleTicket ticket = new TroubleTicket();
                                    ticket.setUserQuestion(request.getQuery());
                                    ticket.setBotResponse(finalAnswer);
                                    ticket.setStatus("pending");
                                    ticketRepository.save(ticket);
                                    System.out.println("检测到新问题，自动创建工单，ID: " + ticket.getId());
                                } else {
                                    System.out.println(String.format("检测到相似问题（最高相似度: %.2f%%，与工单 #%d 冲突），自动过滤合并。", maxSim * 100, duplicateId));
                                }
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

    // 💡 经典 Levenshtein 距离算法（计算两句中文的相似度 0.0 ~ 1.0）
    private static int getLevenshteinDistance(CharSequence s, CharSequence t) {
        if (s == null || t == null) return 0;
        int n = s.length(), m = t.length();
        if (n == 0) return m;
        if (m == 0) return n;
        int[] p = new int[n + 1], d = new int[n + 1], _d;
        int i, j, cost;
        char t_j;
        for (i = 0; i <= n; i++) p[i] = i;
        for (j = 1; j <= m; j++) {
            t_j = t.charAt(j - 1);
            d[0] = j;
            for (i = 1; i <= n; i++) {
                cost = s.charAt(i - 1) == t_j ? 0 : 1;
                d[i] = Math.min(Math.min(d[i - 1] + 1, p[i] + 1), p[i - 1] + cost);
            }
            _d = p; p = d; d = _d;
        }
        return p[n];
    }

    private static double getSimilarity(String s1, String s2) {
        if (s1 == null || s2 == null) return 0.0;
        s1 = s1.trim(); s2 = s2.trim();
        int distance = getLevenshteinDistance(s1, s2);
        int maxLength = Math.max(s1.length(), s2.length());
        if (maxLength == 0) return 1.0;
        return 1.0 - ((double) distance / maxLength);
    }
}

class ChatRequest {
    private String query;
    private Integer topK = 5;
    private Boolean stream = true;
    private List<HistoryMessage> history;

    public String getQuery() { return query; }
    public void setQuery(String query) { this.query = query; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public Boolean getStream() { return stream; }
    public void setStream(Boolean stream) { this.stream = stream; }
    public List<HistoryMessage> getHistory() { return history; }
    public void setHistory(List<HistoryMessage> history) { this.history = history; }
}

class HistoryMessage {
    private String role;
    private String content;

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
}