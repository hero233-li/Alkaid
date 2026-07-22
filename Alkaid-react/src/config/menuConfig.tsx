import { lazy, Suspense, type ReactNode } from 'react';
import type { MenuProps } from 'antd';
import {
  CalendarClock,
  ClipboardList,
  ClipboardCheck,
  Database,
  Home,
  Layers,
  Link2,
  PackagePlus,
  SendHorizontal,
  Search,
  Settings,
  GraduationCap,
  Workflow,
} from 'lucide-react';
import PlaceholderPage from '../pages/PlaceholderPage';
import { ENABLE_HIGH_FREQUENCY } from './runtimeConfig';

const InterfaceWorkbenchPage = lazy(() => import('../pages/InterfaceWorkbenchPage'));
const BusinessAccessPage = lazy(() => import('../pages/BusinessAccessPage'));
const ProductApplyPage = lazy(() => import('../pages/ProductApplyPage'));
const SystemSettingsPage = lazy(() => import('../pages/SystemSettingsPage'));
const WelcomePage = lazy(() => import('../pages/WelcomePage'));
const WorkflowLearningPage = lazy(() => import('../pages/WorkflowLearningPage'));
const ApplicationLinkGeneratorPage = lazy(() => import('../pages/ApplicationLinkGeneratorPage'));
const VerificationApprovalPage = lazy(() => import('../pages/VerificationApprovalPage'));
const ApplicationDataGeneratorPage = lazy(() => import('../pages/ApplicationDataGeneratorPage'));
const CardStatusProcessingPage = lazy(() => import('../pages/CardStatusProcessingPage'));
const LoanStatusProcessingPage = lazy(() => import('../pages/LoanStatusProcessingPage'));
const HighFrequencyTransactionPage = lazy(() => import('../pages/HighFrequencyTransactionPage'));
const TaskCenterPage = lazy(() => import('../pages/TaskCenterPage'));

export const DEFAULT_MENU_KEY = 'home';
export const DEFAULT_OPEN_MENU_KEYS = ['product-data', 'automation', 'system'];

export interface MenuRenderContext {
  onNavigate: (menuKey: string) => void;
  tabKey: string;
  unavailableMenuKeys: string[];
}

export interface AppMenuNode {
  key: string;
  label: string;
  route?: string;
  icon?: ReactNode;
  closable?: boolean;
  visibilityConfigurable?: boolean;
  children?: AppMenuNode[];
  render?: (context: MenuRenderContext) => ReactNode;
}

export const appMenuTree: AppMenuNode[] = [
  {
    key: 'home',
    label: '首页',
    route: '/',
    icon: <Home size={18} />,
    closable: false,
    render: ({ onNavigate, unavailableMenuKeys }) => (
      <WelcomePage
        shortcuts={getHomeShortcutCandidates(unavailableMenuKeys)}
        onNavigate={onNavigate}
      />
    ),
  },
  {
    key: 'product-data',
    label: '产品造数',
    icon: <PackagePlus size={18} />,
    children: [
      {
        key: 'product-application',
        label: '产品申请',
        route: '/product-data/product-application',
        icon: <PackagePlus size={18} />,
        render: ({ tabKey }) => <ProductApplyPage pageInstanceKey={tabKey} />,
      },
      {
        key: 'business-access-query',
        label: '业务准入查询',
        route: '/product-data/business-access',
        icon: <Search size={18} />,
        render: () => <BusinessAccessPage />,
      },
      {
        key: 'application-link-generator',
        label: '申请链接生成',
        route: '/product-data/application-links',
        icon: <Link2 size={18} />,
        render: () => <ApplicationLinkGeneratorPage />,
      },
      {
        key: 'verification-approval',
        label: '核实审批',
        route: '/product-data/verification-approval',
        icon: <ClipboardCheck size={18} />,
        render: () => <VerificationApprovalPage />,
      },
      {
        key: 'application-data-generator',
        label: '申请数据生成',
        route: '/product-data/application-data',
        icon: <Database size={18} />,
        render: () => <ApplicationDataGeneratorPage />,
      },
      {
        key: 'card-status-processing',
        label: '卡状态处理',
        route: '/product-data/card-status',
        icon: <Database size={18} />,
        render: () => <CardStatusProcessingPage />,
      },
      {
        key: 'loan-status-processing',
        label: '贷款状态处理',
        route: '/product-data/loan-status',
        icon: <Database size={18} />,
        render: () => <LoanStatusProcessingPage />,
      },
      ...(ENABLE_HIGH_FREQUENCY
        ? [
            {
              key: 'post-loan-processing',
              label: '高频交易',
              icon: <Workflow size={18} />,
              children: [
                {
                  key: 'high-frequency-transaction',
                  label: 'Risk050009',
                  route: '/product-data/high-frequency/risk050009',
                  icon: <Database size={18} />,
                  render: () => <HighFrequencyTransactionPage />,
                },
              ],
            },
          ]
        : []),
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
        route: '/automation/workflow-learning',
        icon: <GraduationCap size={18} />,
        render: () => <WorkflowLearningPage />,
      },
      {
        key: 'workflow',
        label: 'Workflow 管理',
        route: '/automation/workflows',
        icon: <Workflow size={18} />,
        render: () => <PlaceholderPage title="Workflow 管理" />,
      },
      {
        key: 'jobs',
        label: '任务中心',
        route: '/automation/jobs',
        icon: <ClipboardList size={18} />,
        render: () => <TaskCenterPage />,
      },
      {
        key: 'batch',
        label: '批量任务',
        route: '/automation/batch',
        icon: <Layers size={18} />,
        render: () => <PlaceholderPage title="批量任务" />,
      },
      {
        key: 'schedule',
        label: '定时任务',
        route: '/automation/schedule',
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
        route: '/data-platform/data',
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
        route: '/system/workbench',
        icon: <SendHorizontal size={18} />,
        render: () => <InterfaceWorkbenchPage />,
      },
      {
        key: 'settings',
        label: '系统设置',
        route: '/system/settings',
        icon: <Settings size={18} />,
        visibilityConfigurable: false,
        render: ({ unavailableMenuKeys }) => {
          const unavailableKeys = new Set(unavailableMenuKeys);
          const shortcutKeys = new Set(
            getHomeShortcutCandidates(unavailableMenuKeys).map((item) => item.key),
          );
          return (
            <SystemSettingsPage
              pages={appMenuLeafNodes
                .filter((item) => !unavailableKeys.has(item.key))
                .map((item) => ({
                  key: item.key,
                  label: item.label,
                  icon: item.icon,
                  configurable:
                    item.visibilityConfigurable !== false && item.key !== DEFAULT_MENU_KEY,
                  homeShortcutConfigurable: shortcutKeys.has(item.key),
                }))}
            />
          );
        },
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

export function getVisibleMenuItems(
  hiddenMenuKeys: string[],
  unavailableMenuKeys: string[] = [],
): MenuProps['items'] {
  const hiddenKeys = new Set([...hiddenMenuKeys, ...unavailableMenuKeys]);
  const filterNodes = (nodes: AppMenuNode[]): AppMenuNode[] =>
    nodes.flatMap((node) => {
      if (!node.children?.length) return hiddenKeys.has(node.key) ? [] : [node];
      const children = filterNodes(node.children);
      return children.length ? [{ ...node, children }] : [];
    });
  return toAntdMenuItems(filterNodes(appMenuTree));
}

const HOME_SHORTCUT_EXCLUDED_KEYS = new Set(['home', 'settings']);

export function getHomeShortcutCandidates(unavailableMenuKeys: string[] = []) {
  const unavailableKeys = new Set(unavailableMenuKeys);
  return appMenuLeafNodes
    .filter((item) => !HOME_SHORTCUT_EXCLUDED_KEYS.has(item.key) && !unavailableKeys.has(item.key))
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

function normalizeRoute(route: string) {
  const path = route.trim() || '/';
  const withLeadingSlash = path.startsWith('/') ? path : `/${path}`;
  return withLeadingSlash.length > 1 ? withLeadingSlash.replace(/\/+$/, '') : withLeadingSlash;
}

export function getMenuRoute(key: string) {
  return appMenuNodeMap.get(key)?.route || '/';
}

export function getMenuKeyByRoute(route: string) {
  const normalizedRoute = normalizeRoute(route);
  return appMenuLeafNodes.find((item) => normalizeRoute(item.route || '/') === normalizedRoute)
    ?.key;
}

export function isMenuLeaf(key: string) {
  return appMenuLeafNodes.some((item) => item.key === key);
}

export function renderMenuPage(key: string, context: MenuRenderContext) {
  const node = appMenuNodeMap.get(key);
  const page = context.unavailableMenuKeys.includes(key) ? (
    <PlaceholderPage title={`${node?.label || key}（当前部署不可用）`} />
  ) : node?.render ? (
    node.render(context)
  ) : (
    <PlaceholderPage title={node?.label || key} />
  );
  return <Suspense fallback={<div className="page-surface">正在加载页面...</div>}>{page}</Suspense>;
}
