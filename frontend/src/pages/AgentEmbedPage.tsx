import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import DashboardLayout from '../layouts/DashboardLayout';
import api from '../lib/api';
import { ClipboardDocumentIcon, CodeBracketIcon, CheckCircleIcon, GlobeAltIcon, Cog6ToothIcon } from '@heroicons/react/24/outline'
import { useTranslation } from '../lib/translations';
import toast from 'react-hot-toast';

interface EmbedConfig {
  embed_enabled: boolean;
  embed_widget_color: string;
  embed_position: string;
  embed_greeting_message: string;
  embed_language: string;
  allowed_domains: string[];
}

interface Agent {
  id: number;
  name: string;
  description: string;
}

export const AgentEmbedPage: React.FC = () => {
  const t = useTranslation();
  const { agentId } = useParams<{ agentId: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [config, setConfig] = useState<EmbedConfig>({
    embed_enabled: false,
    embed_widget_color: '#4F46E5',
    embed_position: 'bottom-right',
    embed_greeting_message: '',
    embed_language: 'en',
    allowed_domains: []
  });
  const [embedCode, setEmbedCode] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [domainInput, setDomainInput] = useState('');

  useEffect(() => {
    loadAgent();
    loadEmbedConfig();
  }, [agentId]);

  const loadAgent = async () => {
    try {
      const response = await api.get(`/agents/${agentId}`);
      setAgent(response.data);
    } catch (error) {
      console.error('Error loading agent:', error);
    }
  };

  const loadEmbedConfig = async () => {
    try {
      const response = await api.get(`/embed/agents/${agentId}/embed-config`);
      setConfig(response.data);
      
      if (response.data.embed_enabled) {
        await loadEmbedCode();
      }
    } catch (error) {
      console.error('Error loading embed config:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadEmbedCode = async () => {
    try {
      const response = await api.get(`/embed/agents/${agentId}/embed-code`);
      setEmbedCode(response.data.embed_code);
    } catch (error) {
      console.error('Error loading embed code:', error);
    }
  };

  const handleSaveConfig = async () => {
    try {
      await api.put(`/embed/agents/${agentId}/embed-config`, config);
      
      if (config.embed_enabled) {
        await loadEmbedCode();
      }
      
      toast.success(t.agentEmbed.saveSuccess);
    } catch (error: any) {
      toast.error(t.agentEmbed.saveError + ': ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    toast.success(t.agentEmbed.codeCopied);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAddDomain = () => {
    if (domainInput && !config.allowed_domains.includes(domainInput)) {
      setConfig({
        ...config,
        allowed_domains: [...config.allowed_domains, domainInput]
      });
      setDomainInput('');
    }
  };

  const handleRemoveDomain = (domain: string) => {
    setConfig({
      ...config,
      allowed_domains: config.allowed_domains.filter(d => d !== domain)
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          {/* Header Skeleton */}
          <div>
            <div className="h-9 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-2"></div>
            <div className="h-5 w-96 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
          </div>

          {/* Config Card Skeleton */}
          <Card>
            <div className="space-y-6">
              <div className="h-6 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
              <div className="h-12 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
              <div className="h-12 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
              <div className="h-12 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
            </div>
          </Card>

          {/* Code Card Skeleton */}
          <Card>
            <div className="space-y-4">
              <div className="h-6 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
              <div className="h-32 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
            </div>
          </Card>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            {t.agentEmbed.title} - {agent?.name || t.common.loading}
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t.common.status === 'Statut' ? 'Configurez et intégrez votre agent vocal dans votre site web' : 'Configure and integrate your voice agent into your website'}
          </p>
        </div>

      {/* Configuration Section */}
      <Card>
        <div className="flex items-center gap-3 mb-6">
          <Cog6ToothIcon className="text-indigo-600 h-6 w-6" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {t.agentEmbed.embedConfiguration}
          </h2>
        </div>

        <div className="space-y-6">
          {/* Enable/Disable */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                {t.agentEmbed.enableEmbed}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {t.common.status === 'Statut' ? 'Autoriser cet agent à être intégré sur les sites web' : 'Allow this agent to be embedded on websites'}
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={config.embed_enabled}
                onChange={(e) => setConfig({ ...config, embed_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 dark:peer-focus:ring-indigo-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-600"></div>
            </label>
          </div>

          {/* Widget Color */}
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              {t.agentEmbed.widgetColor}
            </label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={config.embed_widget_color}
                onChange={(e) => setConfig({ ...config, embed_widget_color: e.target.value })}
                className="h-10 w-20 border-2 border-gray-300 dark:border-gray-600 rounded cursor-pointer"
              />
              <input
                type="text"
                value={config.embed_widget_color}
                onChange={(e) => setConfig({ ...config, embed_widget_color: e.target.value })}
                className="flex-1 px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                placeholder="#4F46E5"
              />
            </div>
          </div>

          {/* Widget Position */}
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              {t.agentEmbed.widgetPosition}
            </label>
            <select
              value={config.embed_position}
              onChange={(e) => setConfig({ ...config, embed_position: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
            >
              <option value="bottom-right">{t.agentEmbed.bottomRight}</option>
              <option value="bottom-left">{t.agentEmbed.bottomLeft}</option>
              <option value="top-right">{t.agentEmbed.topRight}</option>
              <option value="top-left">{t.agentEmbed.topLeft}</option>
            </select>
          </div>

          {/* Widget Language */}
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              {t.common.status === 'Statut' ? 'Langue de l\'interface' : 'UI Language'}
            </label>
            <select
              value={config.embed_language}
              onChange={(e) => setConfig({ ...config, embed_language: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
            >
              <option value="en">English</option>
              <option value="fr">Français</option>
              <option value="es">Español</option>
              <option value="de">Deutsch</option>
              <option value="it">Italiano</option>
              <option value="pt">Português</option>
              <option value="zh">中文</option>
              <option value="ja">日本語</option>
              <option value="ko">한국어</option>
            </select>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              {t.common.status === 'Statut' ? 'Sélectionnez la langue de l\'interface utilisateur du widget' : 'Select the language for the widget user interface'}
            </p>
          </div>

          {/* Greeting Message */}
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              {t.agentEmbed.greetingMessage}
            </label>
            <textarea
              value={config.embed_greeting_message}
              onChange={(e) => setConfig({ ...config, embed_greeting_message: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
              rows={3}
              placeholder={`Hi! I'm ${agent?.name}. How can I help you?`}
            />
          </div>

          {/* Allowed Domains */}
          <div>
            <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
              {t.agentEmbed.allowedDomains} ({t.common.status === 'Statut' ? 'Optionnel' : 'Optional'})
            </label>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              {t.common.status === 'Statut' ? 'Restreignez les sites web qui peuvent intégrer cet agent. Laissez vide pour autoriser tous les domaines.' : 'Restrict which websites can embed this agent. Leave empty to allow all domains.'}
            </p>
            
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={domainInput}
                onChange={(e) => setDomainInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddDomain()}
                className="flex-1 px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                placeholder={t.agentEmbed.domainPlaceholder}
              />
              <Button onClick={handleAddDomain} variant="outline">
                {t.agentEmbed.addDomain}
              </Button>
            </div>

            {config.allowed_domains.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {config.allowed_domains.map((domain) => (
                  <div
                    key={domain}
                    className="flex items-center gap-2 px-3 py-1 bg-indigo-100 dark:bg-indigo-900 text-indigo-800 dark:text-indigo-200 rounded-full"
                  >
                    <GlobeAltIcon className="h-3.5 w-3.5" />
                    <span className="text-sm">{domain}</span>
                    <button
                      onClick={() => handleRemoveDomain(domain)}
                      className="text-indigo-600 dark:text-indigo-300 hover:text-indigo-800"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Save Button */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <Button onClick={handleSaveConfig} className="w-full">
              <CheckCircleIcon className="mr-2 h-4 w-4" />
              {t.agentEmbed.saveConfig}
            </Button>
          </div>
        </div>
      </Card>

      {/* Embed Code Section */}
      {config.embed_enabled && embedCode && (
        <Card>
          <div className="flex items-center gap-3 mb-6">
            <CodeBracketIcon className="text-indigo-600 h-6 w-6" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {t.agentEmbed.embedCode}
            </h2>
          </div>

          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {t.common.status === 'Statut' ? 'Copiez et collez cet extrait de code dans le HTML de votre site web, juste avant la balise de fermeture' : 'Copy and paste this code snippet into your website\'s HTML, just before the closing'} &lt;/body&gt; {t.common.status === 'Statut' ? 'tag.' : 'tag.'}
            </p>

            <div className="relative">
              <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm">
                <code>{embedCode}</code>
              </pre>
              <Button
                onClick={handleCopyCode}
                className="absolute top-2 right-2"
                size="sm"
                variant="outline"
              >
                {copied ? (
                  <>
                    <CheckCircleIcon className="mr-2 h-4 w-4" />
                    {t.agentEmbed.codeCopied}
                  </>
                ) : (
                  <>
                    <ClipboardDocumentIcon className="mr-2 h-4 w-4" />
                    {t.agentEmbed.copyCode}
                  </>
                )}
              </Button>
            </div>

            {/* Installation Instructions */}
            <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
              <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">
                {t.common.status === 'Statut' ? 'Instructions d\'installation' : 'Installation Instructions'}
              </h3>
              <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800 dark:text-blue-300">
                <li>{t.common.status === 'Statut' ? 'Copiez le code d\'intégration ci-dessus' : 'Copy the embed code above'}</li>
                <li>{t.common.status === 'Statut' ? 'Ouvrez le fichier HTML de votre site web' : 'Open your website\'s HTML file'}</li>
                <li>{t.common.status === 'Statut' ? 'Collez le code juste avant la balise de fermeture' : 'Paste the code just before the closing'} &lt;/body&gt; {t.common.status === 'Statut' ? 'tag' : 'tag'}</li>
                <li>{t.common.status === 'Statut' ? 'Enregistrez et déployez votre site web' : 'Save and deploy your website'}</li>
                <li>{t.common.status === 'Statut' ? 'Le widget de l\'agent vocal apparaîtra sur votre site web !' : 'The voice agent widget will appear on your website!'}</li>
              </ol>
            </div>

            {/* Preview */}
            <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                {t.common.status === 'Statut' ? 'Aperçu' : 'Preview'}
              </h3>
              <div className="flex items-center gap-3">
                <div
                  className="w-16 h-16 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: config.embed_widget_color }}
                >
                  <GlobeAltIcon className="text-white h-8 w-8" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {t.common.status === 'Statut' ? 'Widget Agent Vocal' : 'Voice Agent Widget'}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {t.common.status === 'Statut' ? 'Position:' : 'Position:'} {config.embed_position === 'bottom-right' ? t.agentEmbed.bottomRight : config.embed_position === 'bottom-left' ? t.agentEmbed.bottomLeft : config.embed_position === 'top-right' ? t.agentEmbed.topRight : t.agentEmbed.topLeft}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    {config.embed_greeting_message || (t.common.status === 'Statut' ? `Bonjour ! Je suis ${agent?.name}. Comment puis-je vous aider ?` : `Hi! I'm ${agent?.name}. How can I help you?`)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {!config.embed_enabled && (
        <Card>
          <div className="text-center py-12">
            <CodeBracketIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              {t.common.status === 'Statut' ? 'Intégration non activée' : 'Embed Not Enabled'}
            </h3>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              {t.common.status === 'Statut' ? 'Activez la fonctionnalité d\'intégration de site web ci-dessus pour générer votre code d\'intégration.' : 'Enable the website embed feature above to generate your embed code.'}
            </p>
          </div>
        </Card>
      )}
      </div>
    </DashboardLayout>
  );
};

