import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Space, Card, Tag, Input as SearchInput } from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { getUsers, createUser, updateUser, deleteUser } from '../../api';

export default function Accounts() {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [searchText, setSearchText] = useState('');
    const [form] = Form.useForm();

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await getUsers();
            setUsers(res.data || []);
        } catch (error) {
            message.error('加载用户列表失败');
            console.error('获取用户列表错误:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleSubmit = async (values) => {
        try {
            if (editingUser) {
                // 编辑时，如果没有填密码就不传
                const updateData = { ...values };
                if (!updateData.password || updateData.password.trim() === '') {
                    delete updateData.password;
                }
                await updateUser(editingUser.id, updateData);
                message.success('更新成功');
            } else {
                // 新增时，密码必填
                if (!values.password || values.password.trim() === '') {
                    message.error('请输入密码');
                    return;
                }
                await createUser(values);
                message.success('创建成功');
            }
            setModalVisible(false);
            form.resetFields();
            fetchUsers();
        } catch (error) {
            message.error(editingUser ? '更新失败' : '创建失败');
            console.error('操作失败:', error);
        }
    };

    const handleDelete = async (id) => {
        Modal.confirm({
            title: '确认删除',
            content: '确定要删除该账号吗？',
            okText: '确定',
            cancelText: '取消',
            onOk: async () => {
                try {
                    await deleteUser(id);
                    message.success('删除成功');
                    fetchUsers();
                } catch (error) {
                    message.error('删除失败');
                    console.error('删除错误:', error);
                }
            },
        });
    };

    const filteredUsers = users.filter(user =>
        user.username?.includes(searchText) ||
        user.realName?.includes(searchText) ||
        user.phone?.includes(searchText)
    );

    const columns = [
        {
            title: '用户名',
            dataIndex: 'username',
            render: (text) => <span style={{ fontWeight: 500 }}>{text}</span>,
        },
        { title: '姓名', dataIndex: 'realName' },
        { title: '手机号', dataIndex: 'phone' },
        {
            title: '状态',
            dataIndex: 'isActive',
            render: (isActive) => (
                <Tag color={isActive ? 'success' : 'warning'}>
                    {isActive ? '启用' : '冻结'}
                </Tag>
            ),
        },
        {
            title: '操作',
            width: 160,
            render: (_, record) => (
                <Space size="small">
                    <Button
                        type="link"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => {
                            setEditingUser(record);
                            form.setFieldsValue(record);
                            setModalVisible(true);
                        }}
                    >
                        编辑
                    </Button>
                    <Button
                        type="link"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDelete(record.id)}
                    >
                        删除
                    </Button>
                </Space>
            ),
        },
    ];

    return (
        <div>
            {/* 页面标题 */}
            <div style={{ marginBottom: 24 }}>
                <h2 style={{ fontSize: 20, fontWeight: 600, color: '#1a1a2e', marginBottom: 4 }}>账号管理</h2>
                <span style={{ color: '#8c8c8c', fontSize: 14 }}>管理运维人员的系统账号</span>
            </div>

            {/* 工具栏 */}
            <Card
                size="small"
                style={{ marginBottom: 16, borderRadius: 12, border: '1px solid #f0f0f0' }}
                bodyStyle={{ padding: '12px 16px' }}
            >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                    <Space>
                        <SearchInput
                            placeholder="搜索用户名/姓名/手机号"
                            prefix={<SearchOutlined style={{ color: '#b0b0b0' }} />}
                            value={searchText}
                            onChange={(e) => setSearchText(e.target.value)}
                            style={{ width: 240, borderRadius: 8 }}
                            allowClear
                        />
                        <Button
                            icon={<ReloadOutlined />}
                            onClick={fetchUsers}
                            style={{ borderRadius: 8 }}
                        >
                            刷新
                        </Button>
                    </Space>
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={() => {
                            setEditingUser(null);
                            form.resetFields();
                            setModalVisible(true);
                        }}
                        style={{ borderRadius: 8, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none' }}
                    >
                        新增账号
                    </Button>
                </div>
            </Card>

            {/* 表格 */}
            <Table
                columns={columns}
                dataSource={filteredUsers}
                loading={loading}
                rowKey="id"
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条记录` }}
                style={{ borderRadius: 12 }}
                rowClassName={() => 'custom-table-row'}
            />

            {/* 弹窗 */}
            <Modal
                title={
                    <span style={{ fontSize: 18, fontWeight: 600 }}>
                        {editingUser ? '编辑账号' : '新增账号'}
                    </span>
                }
                open={modalVisible}
                onCancel={() => setModalVisible(false)}
                footer={null}
                style={{ borderRadius: 16 }}
            >
                <Form form={form} onFinish={handleSubmit} layout="vertical">
                    <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
                        <Input placeholder="请输入用户名" style={{ borderRadius: 8 }} disabled={!!editingUser} />
                    </Form.Item>
                    <Form.Item name="realName" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
                        <Input placeholder="请输入姓名" style={{ borderRadius: 8 }} />
                    </Form.Item>
                    <Form.Item 
                        name="password" 
                        label="密码" 
                        rules={[
                            { required: !editingUser, message: '请输入密码' },
                            { min: 6, message: '密码至少6位' }
                        ]}
                    >
                        <Input.Password 
                            placeholder={editingUser ? "不修改请留空" : "请输入密码"} 
                            style={{ borderRadius: 8 }} 
                        />
                    </Form.Item>
                    <Form.Item name="phone" label="手机号">
                        <Input placeholder="请输入手机号" style={{ borderRadius: 8 }} />
                    </Form.Item>
                    <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                        <Button onClick={() => setModalVisible(false)} style={{ marginRight: 8, borderRadius: 8 }}>
                            取消
                        </Button>
                        <Button
                            type="primary"
                            htmlType="submit"
                            style={{ borderRadius: 8, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none' }}
                        >
                            提交
                        </Button>
                    </Form.Item>
                </Form>
            </Modal>

            <style>{`
                .custom-table-row:hover {
                    background: #f8f9ff !important;
                }
            `}</style>
        </div>
    );
}