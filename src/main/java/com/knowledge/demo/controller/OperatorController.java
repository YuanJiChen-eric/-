package com.knowledge.demo.controller;


import java.util.List;

import org.mindrot.jbcrypt.BCrypt;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.knowledge.demo.entity.Operator;
import com.knowledge.demo.repository.OperatorRepository;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/operators")
@CrossOrigin(origins = "*") // 解决跨域问题，方便前端调试
public class OperatorController {

    @Autowired
    private OperatorRepository operatorRepository;

    // 1. 增：创建运维账号
    @PostMapping
    public ResponseEntity<?> createOperator(@Valid @RequestBody Operator operator) {
        if (operatorRepository.findByUsername(operator.getUsername()) != null) {
            return ResponseEntity.badRequest().body("用户名已存在");
        }
        // 使用 BCrypt 加密密码
        String hashedPwd = BCrypt.hashpw(operator.getPassword(), BCrypt.gensalt());
        operator.setPassword(hashedPwd);
        operator.setIsActive(true);
        operatorRepository.save(operator);
        return ResponseEntity.ok("账号创建成功");
    }

    // 2. 删：冻结运维账号
    @DeleteMapping("/{id}")
    public ResponseEntity<?> freezeOperator(@PathVariable Long id) {
        return operatorRepository.findById(id).map(op -> {
            op.setIsActive(false); // 软删除，即“冻结”
            operatorRepository.save(op);
            return ResponseEntity.ok("账号已成功冻结");
        }).orElse(ResponseEntity.notFound().build());
    }

    // 3. 改：修改账号信息
    @PutMapping("/{id}")
    public ResponseEntity<?> updateOperator(@PathVariable Long id, @RequestBody Operator updatedData) {
        return operatorRepository.findById(id).map(op -> {
            if (updatedData.getRealName() != null) op.setRealName(updatedData.getRealName());
            if (updatedData.getPhone() != null) op.setPhone(updatedData.getPhone());
            // 如果修改了密码，需重新加密
            if (updatedData.getPassword() != null && !updatedData.getPassword().isBlank()) {
                op.setPassword(BCrypt.hashpw(updatedData.getPassword(), BCrypt.gensalt()));
            }
            operatorRepository.save(op);
            return ResponseEntity.ok("账号修改成功");
        }).orElse(ResponseEntity.notFound().build());
    }

    // 4. 查：获取所有未冻结账号 / 获取特定账号
    @GetMapping
    public List<Operator> getActiveOperators() {
        return operatorRepository.findByIsActive(true);
    }
}