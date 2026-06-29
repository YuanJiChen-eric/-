import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, message, Modal, Form, Avatar, Space, Tag, Typography } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, ExclamationCircleOutlined, CustomerServiceOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';

const { TextArea } = Input;
const { Text } = Typography;

export default function Chat() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [transferVisible, setTransferVisible] = useState(false);
    const [currentQuestion, setCurrentQuestion] = useState('');
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim()) return;
        const userMsg = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const response = await fetch('http://localhost:8082/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: input,
                    history: messages.map((m) => ({
                        role: m.role,
                        content: m.content,
                    })),
                }),
            });

            if (!response.ok) {
                throw new Error('网络请求失败');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let accumulatedText = '';
            const aiMsgId = Date.now();

            setMessages(prev => [...prev, { role: 'ai', content: '', id: aiMsgId }]);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('event:system')) {
                        const nextLineIndex = lines.indexOf(line) + 1;
                        if (nextLineIndex < lines.length && lines[nextLineIndex].startsWith('data:')) {
                            try {
                                const systemData = JSON.parse(lines[nextLineIndex].substring(5));
                                if (systemData.action === 'transfer_to_human') {
                                    message.warning('此问题需要人工处理，已为您创建工单');
                                    setCurrentQuestion(input);
                                    setTimeout(() => {
                                        setTransferVisible(true);
                                    }, 1000);
                                }
                            } catch (e) {
                                console.error('解析系统消息失败:', e);
                            }
                        }
                        continue;
                    }
                    
                    if (line.startsWith('data:')) {
                        let content = line.substring(5);
                        if (content.startsWith(' ')) {
                            content = content.slice(1);
                        }
                        if (content === '[DONE]') continue;

                        accumulatedText += (accumulatedText ? '\n' : '') + content;
                        
                        setMessages(prev => 
                            prev.map(msg => 
                                msg.id === aiMsgId 
                                    ? { ...msg, content: accumulatedText }
                                    : msg
                            )
                        );
                    }
                }
            }

        } catch (error) {
            message.error('问答失败，请稍后重试');
            console.error('聊天错误:', error);
            setMessages(prev => 
                prev.filter(msg => msg.content !== '')
            );
        } finally {
            setLoading(false);
        }
    };

    const handleTransfer = (lastAiMessage) => {
        setCurrentQuestion(lastAiMessage);
        setTransferVisible(true);
    };

    const submitTransfer = async (values) => {
        try {
            message.info('转人工功能开发中，请直接联系运维人员');
            setTransferVisible(false);
        } catch (error) {
            message.error('提交失败');
            console.error('转人工错误:', error);
        }
    };

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* 聊天头部 */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: 16,
                borderBottom: '1px solid #f0f0f0',
                marginBottom: 16,
            }}>
                <Space>
                    <div style={{
                        width: 40,
                        height: 40,
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                    }}>
                        <RobotOutlined style={{ fontSize: 20 }} />
                    </div>
                    <div>
                        <div style={{ fontWeight: 600, fontSize: 16, color: '#1a1a2e' }}>运维智能助手</div>
                        <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                            {loading ? '思考中...' : '在线 · 随时为您服务'}
                        </div>
                    </div>
                </Space>
                <Tag color="green" style={{ borderRadius: 12, padding: '2px 12px' }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#52c41a', marginRight: 6 }}></span>
                    AI 驱动
                </Tag>
            </div>

            {/* 消息列表 */}
            <div style={{
                flex: 1,
                overflowY: 'auto',
                paddingRight: 8,
                marginBottom: 16,
                maxHeight: 'calc(70vh - 200px)',
            }}>
                {messages.length === 0 && (
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                        color: '#b0b0b0',
                    }}>
                        <RobotOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
                        <Text type="secondary">您好！我是运维智能助手</Text>
                        <Text type="secondary" style={{ fontSize: 13 }}>请输入您的问题，我将为您提供帮助</Text>
                    </div>
                )}
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        style={{
                            display: 'flex',
                            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                            marginBottom: 16,
                        }}
                    >
                        {msg.role === 'ai' && (
                            <Avatar
                                icon={<RobotOutlined />}
                                style={{
                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                    flexShrink: 0,
                                    marginRight: 12,
                                }}
                            />
                        )}
                        <div
                            style={{
                                maxWidth: '75%',
                                padding: '12px 16px',
                                borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                                background: msg.role === 'user'
                                    ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                                    : '#f5f6fa',
                                color: msg.role === 'user' ? '#fff' : '#1a1a2e',
                                boxShadow: msg.role === 'user'
                                    ? '0 4px 12px rgba(102, 126, 234, 0.3)'
                                    : '0 2px 8px rgba(0,0,0,0.04)',
                                wordBreak: 'break-word',
                            }}
                        >
                            {msg.role === 'ai' ? (
                                <>
                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                    <Button
                                        size="small"
                                        type="link"
                                        icon={<CustomerServiceOutlined />}
                                        onClick={() => handleTransfer(msg.content)}
                                        style={{ paddingLeft: 0, marginTop: 8, color: '#667eea' }}
                                    >
                                        问题未解决？转人工
                                    </Button>
                                </>
                            ) : (
                                <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                            )}
                        </div>
                        {msg.role === 'user' && (
                            <Avatar
                                icon={<UserOutlined />}
                                style={{
                                    background: '#e8e8e8',
                                    color: '#8c8c8c',
                                    flexShrink: 0,
                                    marginLeft: 12,
                                }}
                            />
                        )}
                    </div>
                ))}
                {loading && (
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
                        <Avatar
                            icon={<RobotOutlined />}
                            style={{
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                flexShrink: 0,
                                marginRight: 12,
                            }}
                        />
                        <div style={{
                            padding: '12px 20px',
                            borderRadius: '16px 16px 16px 4px',
                            background: '#f5f6fa',
                            color: '#8c8c8c',
                        }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                正在思考
                <span style={{
                    display: 'inline-block',
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: '#667eea',
                    animation: 'pulse 1.4s infinite',
                    marginLeft: 4,
                }}></span>
                <span style={{
                    display: 'inline-block',
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: '#667eea',
                    animation: 'pulse 1.4s infinite 0.2s',
                }}></span>
                <span style={{
                    display: 'inline-block',
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: '#667eea',
                    animation: 'pulse 1.4s infinite 0.4s',
                }}></span>
              </span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* 输入区域 */}
            <div style={{
                display: 'flex',
                gap: 12,
                paddingTop: 16,
                borderTop: '1px solid #f0f0f0',
            }}>
                <TextArea
                    rows={2}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onPressEnter={(e) => {
                        if (!e.shiftKey) {
                            e.preventDefault();
                            sendMessage();
                        }
                    }}
                    placeholder="输入您的问题，例如：账号冻结怎么处理？"
                    style={{
                        borderRadius: 12,
                        resize: 'none',
                        borderColor: '#e8e8e8',
                        fontSize: 14,
                    }}
                />
                <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={sendMessage}
                    loading={loading}
                    style={{
                        borderRadius: 12,
                        padding: '0 24px',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        height: 'auto',
                        minHeight: 56,
                    }}
                >
                    发送
                </Button>
            </div>

            {/* 转人工弹窗 */}
            <Modal
                title={
                    <Space>
                        <ExclamationCircleOutlined style={{ color: '#faad14' }} />
                        转人工
                    </Space>
                }
                open={transferVisible}
                onCancel={() => setTransferVisible(false)}
                footer={null}
                style={{ borderRadius: 16 }}
            >
                <Form onFinish={submitTransfer} layout="vertical">
                    <Form.Item
                        name="description"
                        label="问题补充说明"
                        rules={[{ required: true, message: '请描述您遇到的问题' }]}
                    >
                        <TextArea rows={4} placeholder="请详细描述您遇到的问题..." style={{ borderRadius: 8 }} />
                    </Form.Item>
                    <Form.Item>
                        <Button
                            type="primary"
                            htmlType="submit"
                            style={{
                                borderRadius: 8,
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                border: 'none',
                            }}
                        >
                            提交
                        </Button>
                    </Form.Item>
                </Form>
            </Modal>

            {/* 动画 keyframes */}
            <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
        </div>
    );
}
