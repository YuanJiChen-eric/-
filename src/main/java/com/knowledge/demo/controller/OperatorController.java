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

    // 5. 新增：运维账号登录接口
    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest loginRequest) {
        // 1. 根据用户名查找用户
        Operator operator = operatorRepository.findByUsername(loginRequest.getUsername());
        if (operator == null) {
            return ResponseEntity.badRequest().body("用户不存在");
        }
        
        // 2. 检查账户是否被冻结（软删除）
        if (!operator.getIsActive()) {
            return ResponseEntity.badRequest().body("该账号已被冻结，请联系管理员");
        }
        
        // 3. 利用 BCrypt 安全验证密码
        if (!BCrypt.checkpw(loginRequest.getPassword(), operator.getPassword())) {
            return ResponseEntity.badRequest().body("用户名或密码错误");
        }
        
        // 4. 安全脱敏：在返回给前端前，抹去密码 hash 值防止泄露
        operator.setPassword(null);
        
        // 5. 返回登录成功的用户对象（包含它的 ID 和 RealName，供前端读取）
        return ResponseEntity.ok(operator);
    }
}

// 类的最下方：直接在这定义 LoginRequest！
// 这样可以彻底删掉外部那个报错的单独 LoginRequest.java 文件，避免路径或重复类冲突！
class LoginRequest {
    private String username;
    private String password;

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
}