import type { ReactNode } from 'react';
import type { MenuProps } from 'antd';
import {
  CalendarClock,
  ClipboardList,
  Database,
  Home,
  Layers,
  Link2,
  Megaphone,
  MousePointerClick,
  PackagePlus,
  SendHorizontal,
  Search,
  Settings,
  GraduationCap,
  Workflow,
} from 'lucide-react';
import InterfaceWorkbenchPage from '../pages/InterfaceWorkbenchPage';
import BusinessAccessPage from '../pages/BusinessAccessPage';
import HomeShortcutManagementPage from '../pages/HomeShortcutManagementPage';
import PlaceholderPage from '../pages/PlaceholderPage';
import ProductApplyPage from '../pages/ProductApplyPage';
import ReleaseManagementPage from '../pages/ReleaseManagementPage';
import SystemSettingsPage from '../pages/SystemSettingsPage';
import WelcomePage from '../pages/WelcomePage';
import WorkflowLearningPage from '../pages/WorkflowLearningPage';
import ApplicationLinkGeneratorPage from '../pages/ApplicationLinkGeneratorPage';
import ApplicationDataGeneratorPage from '../pages/ApplicationDataGeneratorPage';
import CardStatusProcessingPage from '../pages/CardStatusProcessingPage';
import LoanStatusProcessingPage from '../pages/LoanStatusProcessingPage';
import HighFrequencyTransactionPage from '../pages/HighFrequencyTransactionPage';

export const DEFAULT_MENU_KEY = 'home';
export const DEFAULT_OPEN_MENU_KEYS = ['product-data', 'automation', 'system'];

export interface MenuRenderContext {
  onNavigate: (menuKey: string) => void;
  tabKey: string;
}

export interface AppMenuNode {
  key: string;
  label: string;
  icon?: ReactNode;
  closable?: boolean;
  children?: AppMenuNode[];
  render?: (context: MenuRenderContext) => ReactNode;
}

export const appMenuTree: AppMenuNode[] = [
  {
    key: 'home',
    label: '首页',
    icon: <Home size={18} />,
    closable: false,
    render: ({ onNavigate }) => <WelcomePage shortcuts={getHomeShortcutCandidates()} onNavigate={onNavigate} />,
  },
  {
    key: 'product-data',
    label: '产品造数',
    icon: <PackagePlus size={18} />,
    children: [
      {
        key: 'product-application',
        label: '产品申请',
        icon: <PackagePlus size={18} />,
        render: ({ tabKey }) => <ProductApplyPage pageInstanceKey={tabKey} />,
      },
      {
        key: 'business-access-query',
        label: '业务准入查询',
        icon: <Search size={18} />,
        render: () => <BusinessAccessPage />,
      },
      {
        key: 'application-link-generator',
        label: '申请链接生成',
        icon: <Link2 size={18} />,
        render: () => <ApplicationLinkGeneratorPage />,
      },
      {
        key: 'application-data-generator',
        label: '申请数据生成',
        icon: <Database size={18} />,
        render: () => <ApplicationDataGeneratorPage />,
      },
      {
        key: 'card-status-processing',
        label: '卡状态处理',
        icon: <Database size={18} />,
        render: () => <CardStatusProcessingPage />,
      },
      {
        key: 'loan-status-processing',
        label: '贷款状态处理',
        icon: <Database size={18} />,
        render: () => <LoanStatusProcessingPage />,
      },
      {
        key: 'post-loan-processing',
        label: '高频交易',
        icon: <Workflow size={18} />,
        children: [
          {
            key: 'high-frequency-transaction',
            label: 'RIsk050009',
            icon: <Database size={18} />,
            render: () => <HighFrequencyTransactionPage />,
          },
        ],
      },
    ],
  },
  {
    key: 'automation',
    label: '自动化任务',
    icon: <Workflow size={18} />,
    children: [
      {
        key: 'workflow-learning',
        label: 'Workflow 学习中心',
        icon: <GraduationCap size={18} />,
        render: () => <WorkflowLearningPage />,
      },
      {
        key: 'workflow',
        label: 'Workflow 管理',
        icon: <Workflow size={18} />,
        render: () => <PlaceholderPage title="Workflow 管理" />,
      },
      {
        key: 'jobs',
        label: '任务中心',
        icon: <ClipboardList size={18} />,
        render: () => <PlaceholderPage title="任务中心" />,
      },
      {
        key: 'batch',
        label: '批量任务',
        icon: <Layers size={18} />,
        render: () => <PlaceholderPage title="批量任务" />,
      },
      {
        key: 'schedule',
        label: '定时任务',
        icon: <CalendarClock size={18} />,
        render: () => <PlaceholderPage title="定时任务" />,
      },
    ],
  },
  {
    key: 'data-platform',
    label: '数据中心',
    icon: <Database size={18} />,
    children: [
      {
        key: 'data',
        label: '数据管理',
        icon: <Database size={18} />,
        render: () => <PlaceholderPage title="数据管理" />,
      },
    ],
  },
  {
    key: 'system',
    label: '系统管理',
    icon: <Settings size={18} />,
    children: [
      {
        key: 'workbench',
        label: '接口工作台',
        icon: <SendHorizontal size={18} />,
        render: () => <InterfaceWorkbenchPage />,
      },
      {
        key: 'release-management',
        label: '版本管理',
        icon: <Megaphone size={18} />,
        render: () => <ReleaseManagementPage />,
      },
      {
        key: 'home-shortcut-management',
        label: '首页入口管理',
        icon: <MousePointerClick size={18} />,
        render: () => <HomeShortcutManagementPage pages={getHomeShortcutCandidates()} />,
      },
      {
        key: 'settings',
        label: '系统设置',
        icon: <Settings size={18} />,
        render: () =>
          <SystemSettingsPage
            pages={appMenuLeafNodes.map((item) => ({
              key: item.key,
              label: item.label,
              configurable: item.closable !== false,
            }))}
          />,
      },
    ],
  },
];

function toAntdMenuItems(nodes: AppMenuNode[]): MenuProps['items'] {
  return nodes.map((node) => {
    return {
      key: node.key,
      icon: node.icon,
      label: node.label,
      children: node.children?.length ? toAntdMenuItems(node.children) : undefined,
    };
  });
}

function flattenMenu(nodes: AppMenuNode[], parentKey?: string) {
  const leafNodes: AppMenuNode[] = [];
  const nodeMap = new Map<string, AppMenuNode>();
  const parentMap = new Map<string, string>();

  const visit = (items: AppMenuNode[], parent?: string) => {
    items.forEach((item) => {
      nodeMap.set(item.key, item);
      if (parent) {
        parentMap.set(item.key, parent);
      }
      if (item.children?.length) {
        visit(item.children, item.key);
      } else {
        leafNodes.push(item);
      }
    });
  };

  visit(nodes, parentKey);
  return { leafNodes, nodeMap, parentMap };
}

const menuIndex = flattenMenu(appMenuTree);

export const appMenuItems = toAntdMenuItems(appMenuTree);
export const appMenuLeafNodes = menuIndex.leafNodes;
export const appMenuNodeMap = menuIndex.nodeMap;
export const appMenuParentMap = menuIndex.parentMap;

const HOME_SHORTCUT_EXCLUDED_KEYS = new Set([
  'home',
  'release-management',
  'home-shortcut-management',
  'settings',
]);

export function getHomeShortcutCandidates() {
  return appMenuLeafNodes
    .filter((item) => !HOME_SHORTCUT_EXCLUDED_KEYS.has(item.key))
    .map((item) => ({ key: item.key, label: item.label, icon: item.icon }));
}

export function getMenuLabel(key: string) {
  return appMenuNodeMap.get(key)?.label || key;
}

export function getMenuClosable(key: string) {
  return appMenuNodeMap.get(key)?.closable !== false;
}

export function getMenuParentKey(key: string) {
  return appMenuParentMap.get(key);
}

export function isMenuLeaf(key: string) {
  return appMenuLeafNodes.some((item) => item.key === key);
}

export function renderMenuPage(key: string, context: MenuRenderContext) {
  const node = appMenuNodeMap.get(key);
  if (node?.render) {
    return node.render(context);
  }
  return <PlaceholderPage title={node?.label || key} />;
}
