import { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined, RobotOutlined } from '@ant-design/icons';
import axios from 'axios';

export default function Login() {
    const [loading, setLoading] = useState(false);

    const onFinish = async (values) => {
        setLoading(true);
        try {
            // 请求我们刚刚在 Java 端写好的 /login 接口
            const response = await axios.post('http://localhost:8082/api/operators/login', {
                username: values.username,
                password: values.password
            });
            
            // 登录成功，将包含 ID 和姓名安全脱敏后的用户数据存入浏览器本地缓存
            localStorage.setItem('currentUser', JSON.stringify(response.data));
            message.success(`欢迎回来，${response.data.realName || '管理员'}！`);
            
            // 跳转到系统主页
            window.location.href = '/'; 
        } catch (error) {
            // 捕获并弹出 Java 抛出的具体报错内容（如：密码错误、账号冻结等）
            const errorMsg = error.response?.data || '登录失败，请重试';
            message.error(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)'
        }}>
            <Card style={{ width: 400, borderRadius: 16, boxShadow: '0 8px 30px rgba(0,0,0,0.1)' }}>
                <div style={{ textAlign: 'center', marginBottom: 24 }}>
                    <div style={{
                        width: 50, height: 50, borderRadius: '50%',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        color: '#fff', marginBottom: 12
                    }}>
                        <RobotOutlined style={{ fontSize: 24 }} />
                    </div>
                    <h2 style={{ margin: 0, color: '#1a1a2e' }}>智能运维申告平台</h2>
                    <span style={{ color: '#8c8c8c', fontSize: 13 }}>运维专区 · 安全身份校验</span>
                </div>

                <Form onFinish={onFinish} size="large">
                    <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                        <Input prefix={<UserOutlined style={{ color: 'rgba(0,0,0,.25)' }} />} placeholder="用户名" />
                    </Form.Item>
                    <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
                        <Input.Password prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />} placeholder="密码" />
                    </Form.Item>
                    <Form.Item>
                        <Button type="primary" htmlType="submit" loading={loading} block style={{
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            border: 'none', height: 44, borderRadius: 8
                        }}>
                            安全登录
                        </Button>
                    </Form.Item>
                </Form>
            </Card>
        </div>
    );
}