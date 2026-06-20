import { Layout, Menu, Avatar, Badge, Space } from 'antd';
import {
    MessageOutlined,
    UserOutlined,
    FileTextOutlined,
    RobotOutlined,
    BellOutlined,
} from '@ant-design/icons';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import Chat from './pages/Chat';
import Accounts from './pages/Admin/Accounts';
import Tickets from './pages/Admin/Tickets';
import './App.css';

const { Header, Content, Sider, Footer } = Layout;

// 菜单项配置
const menuItems = [
    { key: '/', icon: <MessageOutlined />, label: '智能问答' },
    { key: '/admin/accounts', icon: <UserOutlined />, label: '账号管理' },
    { key: '/admin/tickets', icon: <FileTextOutlined />, label: '工单处理' },
];

// 提取主布局为独立组件，这样可以使用 useLocation
function AppLayout() {
    const location = useLocation();

    return (
        <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
            {/* 顶部导航 */}
            <Header style={{
                background: 'rgba(255,255,255,0.85)',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 24px',
                position: 'sticky',
                top: 0,
                zIndex: 100,
                borderBottom: '1px solid rgba(0,0,0,0.04)',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                        width: 40,
                        height: 40,
                        borderRadius: 12,
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontSize: 20,
                        fontWeight: 'bold',
                    }}>
                        <RobotOutlined />
                    </div>
                    <div>
                        <span style={{ fontSize: 18, fontWeight: 700, color: '#1a1a2e' }}>运维数字员工</span>
                        <span style={{ fontSize: 12, color: '#8c8c8c', marginLeft: 8 }}>AI 智能运维平台</span>
                    </div>
                </div>
                <Space size={16}>
                    <Badge dot>
                        <BellOutlined style={{ fontSize: 18, color: '#5a5a7a', cursor: 'pointer' }} />
                    </Badge>
                    <Avatar
                        style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', cursor: 'pointer' }}
                        icon={<UserOutlined />}
                    />
                </Space>
            </Header>

            <Layout style={{ padding: '20px 24px', gap: 20 }}>
                {/* 侧边栏 */}
                <Sider
                    width={220}
                    style={{
                        background: 'rgba(255,255,255,0.85)',
                        backdropFilter: 'blur(10px)',
                        borderRadius: 16,
                        padding: '12px 0',
                        boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
                        height: 'calc(100vh - 120px)',
                        position: 'sticky',
                        top: 80,
                        border: '1px solid rgba(0,0,0,0.04)',
                    }}
                >
                    <Menu
                        mode="inline"
                        selectedKeys={[location.pathname]}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            padding: '8px 12px',
                        }}
                        items={menuItems.map(item => ({
                            ...item,
                            label: <Link to={item.key} style={{ fontSize: 15, fontWeight: 500 }}>{item.label}</Link>,
                        }))}
                    />
                    <div style={{
                        position: 'absolute',
                        bottom: 20,
                        left: 20,
                        right: 20,
                        padding: '12px 16px',
                        background: 'rgba(102, 126, 234, 0.08)',
                        borderRadius: 10,
                        border: '1px solid rgba(102, 126, 234, 0.15)',
                    }}>
                        <div style={{ fontSize: 12, color: '#8c8c8c' }}>系统状态</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                            <span style={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                background: '#52c41a',
                                display: 'inline-block',
                            }}></span>
                            <span style={{ fontSize: 13, color: '#1a1a2e' }}>所有服务运行中</span>
                        </div>
                    </div>
                </Sider>

                {/* 主内容 */}
                <Content style={{
                    background: 'rgba(255,255,255,0.85)',
                    backdropFilter: 'blur(10px)',
                    borderRadius: 16,
                    padding: 24,
                    boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
                    minHeight: 'calc(100vh - 120px)',
                    border: '1px solid rgba(0,0,0,0.04)',
                }}>
                    <Routes>
                        <Route path="/" element={<Chat />} />
                        <Route path="/admin/accounts" element={<Accounts />} />
                        <Route path="/admin/tickets" element={<Tickets />} />
                    </Routes>
                </Content>
            </Layout>

            <Footer style={{
                textAlign: 'center',
                background: 'transparent',
                color: '#8c8c8c',
                fontSize: 13,
                padding: '12px 0',
                borderTop: '1px solid rgba(0,0,0,0.04)',
            }}>
                运维数字员工平台 v2.0 · 基于 AI + RAG 构建
            </Footer>
        </Layout>
    );
}

// 主 App 组件只负责路由包裹
function App() {
    return (
        <BrowserRouter>
            <AppLayout />
        </BrowserRouter>
    );
}

export default App;