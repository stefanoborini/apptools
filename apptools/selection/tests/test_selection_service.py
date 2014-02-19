from traits.api import Any, Event, HasTraits, Instance, List, provides, Str
from traits.testing.unittest_tools import unittest

from apptools.selection.api import (IDConflictError, ISelection,
    ISelectionProvider, ListenerNotConnectedError,
    ProviderNotRegisteredError, SelectionService)


@provides(ISelection)
class BogusSelection(HasTraits):

    source_id = Str

    # Some content to check that two selections are the same
    content = Any

    def is_empty(self):
        """ Is the selection empty? """
        return False


@provides(ISelectionProvider)
class BogusSelectionProvider(HasTraits):

    #### 'ISelectionProvider' protocol ########################################

    id = Str

    selection = Event

    def get_selection(self):
        return BogusSelection(source_id=self.id, content='get_selection')

    #### 'BogusSelectionProvider' protocol ####################################

    def set_selection(self, content):
        self.selection = BogusSelection(source_id=self.id, content=content)


class BogusListener(HasTraits):
    selections = List

    def on_selection_changed(self, id, selection):
        self.selections.append(selection)


class TestSelectionService(unittest.TestCase):

    def test_add_selection_provider(self):
        service = SelectionService()
        provider = BogusSelectionProvider()

        service.add_selection_provider(provider)
        self.assertTrue(service.has_selection_provider(provider.id))

    def test_add_selection_id_conflict(self):
        service = SelectionService()

        provider_id = 'Foo'
        provider = BogusSelectionProvider(id=provider_id)
        another_provider = BogusSelectionProvider(id=provider_id)

        service.add_selection_provider(provider)
        with self.assertRaises(IDConflictError):
            service.add_selection_provider(another_provider)

    def test_remove_selection_provider(self):
        service = SelectionService()
        provider = BogusSelectionProvider(id='Bogus')

        service.add_selection_provider(provider)
        service.remove_selection_provider(provider)
        self.assertFalse(service.has_selection_provider(provider.id))

        with self.assertRaises(ProviderNotRegisteredError):
            service.remove_selection_provider(provider)

    def test_get_selection(self):
        service = SelectionService()
        provider_id = 'Bogus'
        provider = BogusSelectionProvider(id=provider_id)
        service.add_selection_provider(provider)

        selection = service.get_selection(provider_id)

        self.assertIsInstance(selection, ISelection)
        self.assertEqual(selection.source_id, provider.id)

    def test_get_selection_id_not_registered(self):
        service = SelectionService()

        with self.assertRaises(ProviderNotRegisteredError):
            service.get_selection('not-registered')

    def test_connect_listener(self):
        service = SelectionService()
        provider_id = 'Bogus'
        provider = BogusSelectionProvider(id=provider_id)
        service.add_selection_provider(provider)

        listener = BogusListener()
        service.connect_selection_listener(provider_id,
                                           listener.on_selection_changed)

        content = [1, 2, 3]
        provider.set_selection(content)

        selections = listener.selections
        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[0].source_id, provider.id)
        self.assertEqual(selections[0].content, content)

    def test_connect_listener_then_add_remove_provider(self):
        service = SelectionService()
        provider_id = 'Bogus'

        # Connect listener before provider is registered.
        listener = BogusListener()
        service.connect_selection_listener(provider_id,
                                           listener.on_selection_changed)

        # When the provider is first added, the listener should receive the
        # initial selection (as returned by provider.get_selection)
        provider = BogusSelectionProvider(id=provider_id)
        expected = provider.get_selection()
        service.add_selection_provider(provider)

        selections = listener.selections
        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[-1].content, expected.content)

        # When the provider changes the selection, the event arrive as usual.
        content = [1, 2, 3]
        provider.set_selection(content)

        self.assertEqual(len(selections), 2)
        self.assertEqual(selections[-1].content, content)

        # When we un-register the provider, a change in selection does not
        # generate a callback.
        service.remove_selection_provider(provider)
        provider.set_selection(content)
        self.assertEqual(len(selections), 2)

        # Finally, we register again and get the current selection.
        service.add_selection_provider(provider)
        self.assertEqual(len(selections), 3)
        self.assertEqual(selections[-1].content, expected.content)

    def test_disconnect_listener(self):
        service = SelectionService()
        provider_id = 'Bogus'
        provider = BogusSelectionProvider(id=provider_id)
        service.add_selection_provider(provider)

        listener = BogusListener()
        service.connect_selection_listener(provider_id,
                                           listener.on_selection_changed)
        service.disconnect_selection_listener(provider_id,
                                              listener.on_selection_changed)

        provider.set_selection([1, 2, 3])

        self.assertEqual(len(listener.selections), 0)

    def test_disconnect_unknown_listener(self):
        service = SelectionService()
        provider_id = 'Bogus'
        provider = BogusSelectionProvider(id=provider_id)
        service.add_selection_provider(provider)

        # First case: there are listeners to a provider, but not the one we
        # pass to the disconnect method
        listener_1 = BogusListener()
        service.connect_selection_listener(provider_id,
                                           listener_1.on_selection_changed)

        listener_2 = BogusListener()
        with self.assertRaises(ListenerNotConnectedError):
            service.disconnect_selection_listener(
                provider_id, listener_2.on_selection_changed)

        # Second case: there is no listener connected to the ID
        with self.assertRaises(ListenerNotConnectedError):
            service.disconnect_selection_listener(
                'does-not-exists', listener_2.on_selection_changed)


if __name__ == '__main__':
    unittest.main()
