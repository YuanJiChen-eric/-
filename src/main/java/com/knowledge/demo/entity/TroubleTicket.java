package com.knowledge.demo.entity;
import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;

@Data
@Entity
@Table(name = "trouble_tickets")
public class TroubleTicket {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(columnDefinition = "TEXT")
    private String userQuestion;    // 用户的提问

    @Column(columnDefinition = "TEXT")
    private String botResponse;     // 机器人的回答（即使回答得不好也记录下来）

    private String status = "pending"; // 状态: pending (待人工处理), resolved (已处理)

    private Long operatorId;        // 处理该工单的运维人员ID

    @Column(columnDefinition = "TEXT")
    private String resolution;      // 人工填写的解决方案

    private LocalDateTime createdAt = LocalDateTime.now();
}