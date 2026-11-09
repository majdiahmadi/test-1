"""Offline tests for the VIGIL provider configuration."""

import os
import unittest
from unittest.mock import patch

from vigil.provider_factory import create_model_client


class ProviderFactoryTests(unittest.TestCase):
    @patch("vigil.provider_factory.OpenAI")
    @patch.dict(
        os.environ,
        {
            "VIGIL_MODEL": "fake-nvidia-model",
            "NVIDIA_API_KEY": "fake-nvidia-key",
        },
        clear=True,
    )
    def test_default_provider_is_nvidia(self, fake_openai):
        client, model, provider = create_model_client()

        self.assertEqual(provider, "nvidia")
        self.assertEqual(model, "fake-nvidia-model")
        self.assertIs(client, fake_openai.return_value)
        fake_openai.assert_called_once_with(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key="fake-nvidia-key",
            timeout=60.0,
            max_retries=1,
        )

    @patch("vigil.provider_factory.OpenAI")
    @patch.dict(
        os.environ,
        {
            "VIGIL_PROVIDER": "deepseek",
            "VIGIL_MODEL": "fake-deepseek-model",
            "DEEPSEEK_API_KEY": "fake-deepseek-key",
        },
        clear=True,
    )
    def test_deepseek_configuration(self, fake_openai):
        _, model, provider = create_model_client()

        self.assertEqual(provider, "deepseek")
        self.assertEqual(model, "fake-deepseek-model")
        self.assertEqual(
            fake_openai.call_args.kwargs["base_url"],
            "https://api.deepseek.com",
        )
        self.assertEqual(
            fake_openai.call_args.kwargs["api_key"],
            "fake-deepseek-key",
        )

    @patch("vigil.provider_factory.OpenAI")
    @patch.dict(
        os.environ,
        {
            "VIGIL_PROVIDER": " OPENAI ",
            "VIGIL_MODEL": "fake-openai-model",
            "OPENAI_API_KEY": "fake-openai-key",
        },
        clear=True,
    )
    def test_openai_name_is_normalized(self, fake_openai):
        _, model, provider = create_model_client()

        self.assertEqual(provider, "openai")
        self.assertEqual(model, "fake-openai-model")
        self.assertEqual(
            fake_openai.call_args.kwargs["base_url"],
            "https://api.openai.com/v1",
        )

    @patch("vigil.provider_factory.OpenAI")
    @patch.dict(
        os.environ,
        {
            "VIGIL_PROVIDER": "unknown",
            "VIGIL_MODEL": "fake-model",
            "NVIDIA_API_KEY": "fake-key",
        },
        clear=True,
    )
    def test_unknown_provider_is_rejected(self, fake_openai):
        with self.assertRaisesRegex(ValueError, "Unknown VIGIL_PROVIDER"):
            create_model_client()

        fake_openai.assert_not_called()

    @patch("vigil.provider_factory.OpenAI")
    @patch.dict(
        os.environ,
        {
            "VIGIL_PROVIDER": "deepseek",
            "VIGIL_MODEL": "fake-model",
        },
        clear=True,
    )
    def test_missing_key_is_rejected(self, fake_openai):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
            create_model_client()

        fake_openai.assert_not_called()

    @patch("vigil.provider_factory.OpenAI")
    @patch.dict(
        os.environ,
        {
            "VIGIL_PROVIDER": "nvidia",
            "NVIDIA_API_KEY": "fake-key",
        },
        clear=True,
    )
    def test_missing_model_is_rejected(self, fake_openai):
        with self.assertRaisesRegex(ValueError, "VIGIL_MODEL"):
            create_model_client()

        fake_openai.assert_not_called()


if __name__ == "__main__":
    unittest.main()