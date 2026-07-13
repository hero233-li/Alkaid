import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const defaultBaseDir = dirname(rootDir);
const envFile = join(rootDir, '.env.local');
const envFileValues = readEnvFile(envFile);
const env = { ...process.env, ...envFileValues };
const args = process.argv.slice(2);
const isWindows = process.platform === 'win32';

if (args.includes('--split')) {
  env.DEV_SPLIT_WINDOWS = 'true';
}

if (args.includes('--print-env')) {
  printStartupConfig(env, envFile, envFileValues);
  process.exit(0);
}

if (args.includes('--worker')) {
  printStartupConfig(env, envFile, envFileValues);
  runWorker(env);
} else {
  printStartupConfig(env, envFile, envFileValues);

  const script = isWindows
    ? join(rootDir, 'scripts', 'windows', 'dev-start.bat')
    : join(rootDir, 'scripts', 'macos', 'dev-start.command');

  const command = isWindows ? 'cmd.exe' : 'zsh';
  const commandArgs = isWindows ? ['/d', '/s', '/c', script] : [script];

  const child = spawn(command, commandArgs, {
    cwd: rootDir,
    env,
    stdio: 'inherit',
  });

  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => {
      child.kill(signal);
    });
  }

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

function runWorker(envValues) {
  const command = isWindows ? 'powershell' : 'zsh';
  const workerScript = isWindows
    ? join(rootDir, 'scripts', 'windows', 'dev-worker.ps1')
    : join(rootDir, 'scripts', 'macos', 'dev-worker.command');
  const workerArgs = isWindows
    ? ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', workerScript]
    : [workerScript];

  const child = spawn(command, workerArgs, {
    cwd: rootDir,
    env: envValues,
    stdio: 'inherit',
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

function readEnvFile(filePath) {
  if (!existsSync(filePath)) {
    return {};
  }

  const result = {};
  const content = readFileSync(filePath, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    const assignment = trimmed.startsWith('export ')
      ? trimmed.slice('export '.length).trimStart()
      : trimmed;
    const separatorIndex = assignment.indexOf('=');
    if (separatorIndex <= 0) {
      continue;
    }

    const key = assignment.slice(0, separatorIndex).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
      continue;
    }

    const rawValue = assignment.slice(separatorIndex + 1);
    result[key] = parseEnvValue(rawValue);
  }

  return result;
}

function parseEnvValue(rawValue) {
  let value = stripInlineComment(rawValue).trim();
  const quote = value.at(0);
  if ((quote === '"' || quote === "'") && value.at(-1) === quote) {
    value = value.slice(1, -1);
  }
  return value;
}

function stripInlineComment(value) {
  let quote = null;
  let escaped = false;

  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\' && quote === '"') {
      escaped = true;
      continue;
    }
    if ((char === '"' || char === "'") && !quote) {
      quote = char;
      continue;
    }
    if (char === quote) {
      quote = null;
      continue;
    }
    if (char === '#' && !quote && (index === 0 || /\s/.test(value[index - 1]))) {
      return value.slice(0, index);
    }
  }

  return value;
}

function printStartupConfig(envValues, filePath, loadedValues) {
  const loadedKeys = Object.keys(loadedValues);
  const backendPython = isWindows
    ? join(rootDir, '.venv', 'Scripts', 'python.exe')
    : join(rootDir, '.venv', 'bin', 'python');
  const runtimeDir = envValues.ALKAID_RUNTIME_DIR || join(defaultBaseDir, 'Alkaid-runtime');
  const celeryAlwaysEager = envValues.CELERY_TASK_ALWAYS_EAGER ?? 'false';
  const startWorker = envValues.DEV_START_WORKER ?? (isTruthy(celeryAlwaysEager) ? 'false' : 'true');
  console.log(`Env file: ${loadedKeys.length > 0 ? filePath : 'not found, using defaults/process env'}`);
  console.log('Runtime config:');
  console.log(`  BACKEND_PYTHON=${backendPython}`);
  console.log(`  DJANGO_SETTINGS_MODULE=${envValues.DJANGO_SETTINGS_MODULE ?? 'config.settings.local'}`);
  console.log(`  DEV_BACKEND_PORT=${envValues.DEV_BACKEND_PORT ?? '8000'}`);
  console.log(`  DEV_FRONTEND_PORT=${envValues.DEV_FRONTEND_PORT ?? '5174'}`);
  console.log(`  ALKAID_RUNTIME_DIR=${runtimeDir}`);
  console.log('MySQL config:');
  for (const key of [
    'MYSQL_HOST',
    'MYSQL_PORT',
    'MYSQL_DATABASE',
    'MYSQL_USER',
    'MYSQL_PASSWORD',
    'MYSQL_SSL_DISABLED',
  ]) {
    console.log(`  ${key}=${maskValue(key, envValues[key] ?? '')}`);
  }
  console.log('Celery config:');
  console.log(`  CELERY_BROKER_URL=${maskUrl(envValues.CELERY_BROKER_URL ?? 'amqp://workflow:workflow@127.0.0.1:5672//')}`);
  console.log(`  CELERY_QUEUE=${envValues.CELERY_QUEUE ?? 'alkaid-local'}`);
  console.log(`  CELERY_TASK_ALWAYS_EAGER=${celeryAlwaysEager}`);
  console.log(`  DEV_START_WORKER=${startWorker}`);
}

function maskValue(key, value) {
  if (key.includes('PASSWORD') && value) {
    return '********';
  }
  return value;
}

function maskUrl(value) {
  return value.replace(/:\/\/([^:/@]+):([^@]+)@/, '://$1:********@');
}

function isTruthy(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
}
