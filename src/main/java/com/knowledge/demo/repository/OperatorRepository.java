package com.knowledge.demo.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.knowledge.demo.entity.Operator;

// 注意：这里是 interface（接口），而不是 class（类）
public interface OperatorRepository extends JpaRepository<Operator, Long> {
    // 这行代码的意思是：根据 isActive 状态来查询运维人员列表
    List<Operator> findByIsActive(Boolean isActive);
    
    // 这行代码的意思是：根据用户名查询特定的运维人员
    Operator findByUsername(String username);
}