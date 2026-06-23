import { useState, useEffect } from 'react';
import { Table, Button, Modal, Input, message, Tag, Space, Card, Badge, Tabs } from 'antd';
// 💡 导入 DeleteOutlined 图标
import { CheckCircleOutlined, ClockCircleOutlined, EyeOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons';
import { getTickets, resolveTicket } from '../../api';
import axios from 'axios'; // 💡 导入 axios 用于发送删除请求

const { TextArea } = Input;

export default function Tickets() {
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(false);
    const [resolveVisible, setResolveVisible] = useState(false);
    const [currentTicket, setCurrentTicket] = useState(null);
    const [solution, setSolution] = useState('');
    const [activeTab, setActiveTab] = useState('pending');

    const fetchTickets = async () => {
        setLoading(true);
        try {
            const res = await getTickets({});
            const allData = res.data || [];
            setTickets(allData);
        } catch (error) {
            message.error('加载工单列表失败');
            console.error('获取工单列表错误:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTickets();
    }, []);

    const handleResolve = async () => {
        const currentUser = JSON.parse(localStorage.getItem('currentUser'));
        const activeOperatorId = currentUser ? currentUser.id : 1;

        try {
            await resolveTicket(currentTicket.id, {
                resolution: solution,
                operatorId: activeOperatorId
            });
            message.success('处理完成，已更新知识库');
            setResolveVisible(false);
            setSolution('');
            fetchTickets();
        } catch (error) {
            message.error('处理失败');
            console.error('处理工单错误:', error);
        }
    };

    // 💡 新增：删除工单逻辑（带确认二次弹窗）
    const handleDeleteTicket = (id) => {
        Modal.confirm({
            title: '确认删除',
            icon: <DeleteOutlined style={{ color: '#ff4d4f' }} />,
            content: `确定要删除工单 #${id} 吗？该操作不可逆。`,
            okText: '确认删除',
            cancelText: '取消',
            okType: 'danger',
            okButtonProps: { style: { borderRadius: 8 } },
            cancelButtonProps: { style: { borderRadius: 8 } },
            onOk: async () => {
                try {
                    // 调用 Java 后端的 DELETE 接口
                    await axios.delete(`http://localhost:8082/api/tickets/${id}`);
                    message.success('工单删除成功');
                    fetchTickets(); // 刷新列表
                } catch (error) {
                    message.error('删除工单失败');
                    console.error('删除工单错误:', error);
                }
            }
        });
    };

    const filteredTickets = tickets.filter(ticket => {
        if (activeTab === 'pending') return ticket.status === 'pending';
        if (activeTab === 'resolved') return ticket.status === 'resolved';
        return true;
    });

    const columns = [
        {
            title: '工单编号',
            dataIndex: 'id',
            render: (id) => <span style={{ fontWeight: 500, color: '#667eea' }}>#{id}</span>,
        },
        {
            title: '用户问题',
            dataIndex: 'userQuestion',
            ellipsis: true,
            render: (text) => <span style={{ maxWidth: 200 }}>{text || '-'}</span>,
        },
        {
            title: 'AI回答',
            dataIndex: 'botResponse',
            ellipsis: true,
            render: (text) => <span style={{ maxWidth: 200 }}>{text || '-'}</span>,
        },
        {
            title: '解决方案',
            dataIndex: 'resolution',
            ellipsis: true,
            render: (text) => text || '-',
        },
        {
            title: '处理人ID',
            dataIndex: 'operatorId',
            render: (text) => text || '-',
        },
        {
            title: '提交时间',
            dataIndex: 'createdAt',
            render: (text) => text ? new Date(text).toLocaleString() : '-',
        },
        {
            title: '状态',
            dataIndex: 'status',
            render: (status) => (
                <Tag
                    icon={status === 'pending' ? <ClockCircleOutlined /> : <CheckCircleOutlined />}
                    color={status === 'pending' ? 'orange' : 'green'}
                    style={{ borderRadius: 12, padding: '2px 12px' }}
                >
                    {status === 'pending' ? '待处理' : '已处理'}
                </Tag>
            ),
        },
        {
            title: '操作',
            width: 180, // 💡 拓宽列宽以完美容纳两个按钮
            render: (_, record) => (
                record.status === 'pending' ? (
                    <Space size="middle">
                        <Button
                            type="primary"
                            size="small"
                            icon={<EyeOutlined />}
                            onClick={() => {
                                setCurrentTicket(record);
                                setResolveVisible(true);
                            }}
                            style={{ borderRadius: 8, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none' }}
                        >
                            处理
                        </Button>
                        {/* 💡 红色删除按钮 */}
                        <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => handleDeleteTicket(record.id)}
                            style={{ borderRadius: 8 }}
                        >
                            删除
                        </Button>
                    </Space>
                ) : (
                    <Space size="middle">
                        <Tag color="default" style={{ borderRadius: 12 }}>已完成</Tag>
                        {/* 💡 红色删除记录按钮 */}
                        <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => handleDeleteTicket(record.id)}
                            style={{ borderRadius: 8 }}
                        >
                            删除记录
                        </Button>
                    </Space>
                )
            ),
        },
    ];

    const tabItems = [
        {
            key: 'pending',
            label: (
                <Space>
                    <ClockCircleOutlined />
                    待处理
                    <Badge count={tickets.filter(t => t.status === 'pending').length} size="small" />
                </Space>
            ),
        },
        {
            key: 'resolved',
            label: (
                <Space>
                    <CheckCircleOutlined />
                    已处理
                    <Badge count={tickets.filter(t => t.status === 'resolved').length} size="small" />
                </Space>
            ),
        },
        {
            key: 'all',
            label: (
                <Space>
                    全部
                    <Badge count={tickets.length} size="small" />
                </Space>
            ),
        },
    ];

    return (
        <div>
            <div style={{ marginBottom: 24 }}>
                <h2 style={{ fontSize: 20, fontWeight: 600, color: '#1a1a2e', marginBottom: 4 }}>工单处理</h2>
                <span style={{ color: '#8c8c8c', fontSize: 14 }}>查看并处理用户的转人工请求</span>
            </div>

            <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                <Card
                    size="small"
                    style={{ flex: 1, borderRadius: 12, border: '1px solid #f0f0f0' }}
                    styles={{ body: { padding: '12px 16px' } }}
                >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#8c8c8c' }}>待处理</span>
                        <Badge count={tickets.filter(t => t.status === 'pending').length} style={{ backgroundColor: '#faad14' }} />
                    </div>
                </Card>
                <Card
                    size="small"
                    style={{ flex: 1, borderRadius: 12, border: '1px solid #f0f0f0' }}
                    styles={{ body: { padding: '12px 16px' } }}
                >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#8c8c8c' }}>已处理</span>
                        <Badge count={tickets.filter(t => t.status === 'resolved').length} style={{ backgroundColor: '#52c41a' }} />
                    </div>
                </Card>
                <Card
                    size="small"
                    style={{ flex: 1, borderRadius: 12, border: '1px solid #f0f0f0' }}
                    styles={{ body: { padding: '12px 16px' } }}
                >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#8c8c8c' }}>总计</span>
                        <Badge count={tickets.length} style={{ backgroundColor: '#667eea' }} />
                    </div>
                </Card>
                <Button
                    icon={<ReloadOutlined />}
                    onClick={fetchTickets}
                    style={{ borderRadius: 8, alignSelf: 'center' }}
                >
                    刷新
                </Button>
            </div>

            <Tabs
                activeKey={activeTab}
                onChange={setActiveTab}
                items={tabItems}
                style={{ marginBottom: 16 }}
            />

            <Table
                columns={columns}
                dataSource={filteredTickets}
                loading={loading}
                rowKey="id"
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条记录` }}
                style={{ borderRadius: 12 }}
                rowClassName={(record) => record.status === 'pending' ? 'pending-row' : ''}
            />

            <Modal
                title={
                    <span style={{ fontSize: 18, fontWeight: 600 }}>
                        处理工单 <span style={{ fontSize: 14, fontWeight: 400, color: '#8c8c8c' }}>#{currentTicket?.id}</span>
                    </span>
                }
                open={resolveVisible}
                onCancel={() => setResolveVisible(false)}
                onOk={handleResolve}
                okText="提交处理"
                cancelText="取消"
                style={{ borderRadius: 16 }}
                okButtonProps={{
                    style: { borderRadius: 8, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none' },
                }}
            >
                <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 13, color: '#8c8c8c' }}>用户问题</div>
                    <div style={{ padding: 12, background: '#f8f9ff', borderRadius: 8, color: '#1a1a2e' }}>
                        {currentTicket?.userQuestion || '无'}
                    </div>
                </div>
                <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 13, color: '#8c8c8c' }}>AI回答</div>
                    <div style={{ padding: 12, background: '#f8f9ff', borderRadius: 8, color: '#1a1a2e' }}>
                        {currentTicket?.botResponse || '无'}
                    </div>
                </div>
                <div>
                    <div style={{ fontSize: 13, color: '#8c8c8c', marginBottom: 8 }}>解决方案</div>
                    <TextArea
                        rows={4}
                        value={solution}
                        onChange={(e) => setSolution(e.target.value)}
                        placeholder="请输入解决方案，提交后将自动更新到知识库..."
                        style={{ borderRadius: 8 }}
                    />
                </div>
            </Modal>

            <style>{`
                .pending-row {
                    background: #fffbf0 !important;
                }
                .pending-row:hover {
                    background: #fff7e6 !important;
                }
            `}</style>
        </div>
    );
}