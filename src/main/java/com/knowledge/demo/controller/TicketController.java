package com.knowledge.demo.controller;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.knowledge.demo.repository.TroubleTicketRepository;

@RestController
@RequestMapping("/api/tickets")
@CrossOrigin(origins = "*")
public class TicketController {

    @Autowired
    private TroubleTicketRepository ticketRepository;

    // 1. 查询所有待处理的工单（供后台显示）
    @GetMapping("/pending")
    public ResponseEntity<?> getPendingTickets() {
        return ResponseEntity.ok(ticketRepository.findByStatus("pending"));
    }

    // 2. 运维人员处理工单，并同步写入知识库
    @PostMapping("/{id}/resolve")
    public ResponseEntity<?> resolveTicket(@PathVariable Long id, @RequestBody ResolveRequest request) {
        return ticketRepository.findById(id).map(ticket -> {
            ticket.setResolution(request.getResolution());
            ticket.setOperatorId(request.getOperatorId());
            ticket.setStatus("resolved");
            ticketRepository.save(ticket);

            // 【核心数据飞轮】：通知成员 C 的 Python 模块将本问答存入向量库
            syncToKnowledgeBase(ticket.getUserQuestion(), request.getResolution());

            return ResponseEntity.ok("工单处理完成，并已同步更新至本地知识库。");
        }).orElse(ResponseEntity.notFound().build());
    }

    private void syncToKnowledgeBase(String question, String answer) {
        try {
            HttpClient client = HttpClient.newHttpClient();
            // 构造传给成员 C 的请求 JSON
            String requestBody = String.format("{\"question\": \"%s\", \"answer\": \"%s\"}", question, answer);
            
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://localhost:8000/api/kb/add")) // 成员 C 提供的添加知识库接口
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .build();
            
            client.sendAsync(request, HttpResponse.BodyHandlers.ofString());
        } catch (Exception e) {
            System.err.println("同步知识库失败: " + e.getMessage());
        }
    }
}

// 接收请求参数的类
class ResolveRequest {
    private String resolution;
    private Long operatorId;
    public String getResolution() { return resolution; }
    public void setResolution(String resolution) { this.resolution = resolution; }
    public Long getOperatorId() { return operatorId; }
    public void setOperatorId(Long operatorId) { this.operatorId = operatorId; }
}