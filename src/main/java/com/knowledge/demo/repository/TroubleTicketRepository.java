package com.knowledge.demo.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.knowledge.demo.entity.TroubleTicket;

public interface TroubleTicketRepository extends JpaRepository<TroubleTicket, Long> {
    // 这行代码的意思是：根据工单状态（如 pending/resolved）查询工单列表
    List<TroubleTicket> findByStatus(String status);
}