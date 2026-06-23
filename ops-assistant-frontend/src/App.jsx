import { useEffect } from 'react';
import { Layout, Menu, Avatar, Badge, Space } from 'antd';
import {
    MessageOutlined,
    UserOutlined,
    FileTextOutlined,
    RobotOutlined,
    BellOutlined,
} from '@ant-design/icons';
import { BrowserRouter, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import Chat from './pages/Chat';
import Accounts from './pages/Admin/Accounts';
import Tickets from './pages/Admin/Tickets';
import Login from './pages/Login';
import './App.css';

const { Header, Content, Sider, Footer } = Layout;

// 1. 主页面布局组件（已集成：展示真实姓名、点击退出登录、以及超级管理员菜单过滤）
function AppLayout() {
    const location = useLocation();

    // 从本地缓存读取当前登录的运维专家姓名和账号名
    const currentUser = JSON.parse(localStorage.getItem('currentUser'));
    const realName = currentUser ? currentUser.realName : '管理员';
    
    // 💡 核心权限判断：只有 username 为 admin 的用户才是超级管理员
    const isAdmin = currentUser && currentUser.username === 'admin';

    // 退出登录函数
    const handleLogout = () => {
        localStorage.removeItem('currentUser'); // 擦除缓存
        window.location.href = '/login';       // 重定向回登录
    };

    // 💡 动态生成菜单项：如果非 admin，自动隐藏账号管理和工单处理！
    const menuItems = [
        { key: '/', icon: <MessageOutlined />, label: '智能问答' },
        ...(isAdmin ? [
            { key: '/admin/accounts', icon: <UserOutlined />, label: '账号管理' },
            { key: '/admin/tickets', icon: <FileTextOutlined />, label: '工单处理' }
        ] : [])
    ];

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
                    <Space style={{ cursor: 'pointer' }} onClick={handleLogout} title="点击退出登录">
                        <Avatar
                            style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
                            icon={<UserOutlined />}
                        />
                        <span style={{ fontSize: 14, color: '#5a5a7a', fontWeight: 500 }}>
                            {realName} (退出)
                        </span>
                    </Space>
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
                        {/* 💡 路由守卫：非 admin 访问后台管理页面，直接拦截并退回智能问答主页 */}
                        <Route path="/admin/accounts" element={isAdmin ? <Accounts /> : <Chat />} />
                        <Route path="/admin/tickets" element={isAdmin ? <Tickets /> : <Chat />} />
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

// 2. 核心路由管理器
function AppRoutes() {
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        const user = localStorage.getItem('currentUser');
        if (!user && location.pathname !== '/login') {
            navigate('/login');
        }
    }, [location.pathname, navigate]);

    return (
        <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={<AppLayout />} />
        </Routes>
    );
}

function App() {
    return (
        <BrowserRouter>
            <AppRoutes />
        </BrowserRouter>
    );
}

export default App;