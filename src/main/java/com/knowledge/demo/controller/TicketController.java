package com.knowledge.demo.controller;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.knowledge.demo.entity.TroubleTicket;
import com.knowledge.demo.repository.TroubleTicketRepository;

@RestController
@RequestMapping("/api/tickets")
@CrossOrigin(origins = "http://localhost:5173")
public class TicketController {

    @Autowired
    private TroubleTicketRepository ticketRepository;

    private final ObjectMapper objectMapper = new ObjectMapper();

    // 1. 查询所有待处理的工单（供后台显示）
    @GetMapping("/pending")
    public ResponseEntity<?> getPendingTickets() {
        return ResponseEntity.ok(ticketRepository.findByStatus("pending"));
    }

    // 2. 查询所有工单（支持按状态过滤）
    @GetMapping
    public ResponseEntity<?> getAllTickets(@RequestParam(required = false) String status) {
        if (status != null && !status.isEmpty()) {
            return ResponseEntity.ok(ticketRepository.findByStatus(status));
        }
        return ResponseEntity.ok(ticketRepository.findAll());
    }

    // 3. 删：删除工单（已处理工单会同步软删除知识库条目）
    @DeleteMapping("/{id}")
    public ResponseEntity<?> deleteTicket(@PathVariable Long id) {
        return ticketRepository.findById(id).map(ticket -> {
            if ("resolved".equals(ticket.getStatus())) {
                softDeleteFromKnowledgeBase(ticket);
            }
            ticketRepository.delete(ticket);
            return ResponseEntity.ok("工单已成功删除，关联知识库条目已同步停用。");
        }).orElse(ResponseEntity.notFound().build());
    }

    // 4. 运维人员处理工单，并同步写入知识库
    @PostMapping("/{id}/resolve")
    public ResponseEntity<?> resolveTicket(@PathVariable Long id, @RequestBody ResolveRequest request) {
        return ticketRepository.findById(id).map(ticket -> {
            ticket.setResolution(request.getResolution());
            ticket.setOperatorId(request.getOperatorId());
            ticket.setStatus("resolved");

            String kbEntryId = syncToKnowledgeBase(id, ticket.getUserQuestion(), request.getResolution());
            if (kbEntryId != null) {
                ticket.setKbEntryId(kbEntryId);
            }
            ticketRepository.save(ticket);

            return ResponseEntity.ok("工单处理完成，并已同步更新至本地知识库。");
        }).orElse(ResponseEntity.notFound().build());
    }

  /** 工单处理完成后写入知识库，返回条目 ID */
    private String syncToKnowledgeBase(Long ticketId, String question, String answer) {
        try {
            HttpClient client = HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)
                    .build();

            Map<String, Object> metadata = new HashMap<>();
            metadata.put("ticket_id", String.valueOf(ticketId));
            metadata.put("source", "ticket");

            Map<String, Object> body = new HashMap<>();
            body.put("question", question);
            body.put("answer", answer);
            body.put("metadata", metadata);

            String requestBody = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:8000/api/kb/add"))
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            System.out.println("知识库同步响应: HTTP " + response.statusCode() + " - " + response.body());

            if (response.statusCode() >= 200 && response.statusCode() < 300) {
                JsonNode json = objectMapper.readTree(response.body());
                if (json.has("id")) {
                    return json.get("id").asText();
                }
            }
        } catch (Exception e) {
            System.err.println("同步知识库失败: " + e.getMessage());
            e.printStackTrace();
        }
        return null;
    }

  /** 删除已处理工单时，软删除知识库中对应条目 */
    private void softDeleteFromKnowledgeBase(TroubleTicket ticket) {
        try {
            HttpClient client = HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)
                    .build();

            Map<String, Object> body = new HashMap<>();
            body.put("ticket_id", ticket.getId());
            if (ticket.getKbEntryId() != null && !ticket.getKbEntryId().isEmpty()) {
                body.put("id", ticket.getKbEntryId());
            }

            String requestBody = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:8000/api/kb/soft-delete"))
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            System.out.println("知识库软删除响应: HTTP " + response.statusCode() + " - " + response.body());
        } catch (Exception e) {
            System.err.println("知识库软删除失败（工单仍将删除）: " + e.getMessage());
            e.printStackTrace();
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
