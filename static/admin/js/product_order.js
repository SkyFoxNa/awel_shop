// static/admin/js/product_order.js
django.jQuery(document).ready(function($) {
    // 1. Активація живого пошуку (Select2) для випадаючих списків компонентів


    // 2. Управління порядком блоків на сторінці товару
    var $form = $('#product_form');
    if (!$form.length) return;

    // Знаходимо всі основні секції (fieldset) та інлайни (inline-group) за їхніми заголовками або ID
    var $photos = $('.inline-group').filter(function() {
        return $(this).find('h2').text().includes('ФОТО ТОВАРУ') || $(this).attr('id').indexOf('photo') !== -1;
    });

    var $mainInfo = $form.find('fieldset').filter(function() {
        return $(this).find('h2').text().includes('Основна інформація');
    });

    var $stocks = $('.inline-group').filter(function() {
        return $(this).find('h2').text().includes('ЗАЛИШКИ') || $(this).attr('id').indexOf('stock') !== -1;
    });

    var $components = $('.inline-group').filter(function() {
        return $(this).find('h2').text().includes('КОМПЛЕКТУ') || $(this).attr('id').indexOf('component') !== -1;
    });

    var $boxing = $('.inline-group').filter(function() {
        return $(this).find('h2').text().includes('ТАРА') || $(this).attr('id').indexOf('boxing') !== -1;
    });

    var $stickers = $('.inline-group').filter(function() {
        return $(this).find('h2').text().includes('НАЛІПКА') || $(this).attr('id').indexOf('sticker') !== -1;
    });

    var $typeProps = $form.find('fieldset').filter(function() {
        return $(this).find('h2').text().includes('Тип та властивості');
    });

    var $links = $form.find('fieldset').filter(function() {
        return $(this).find('h2').text().includes('Зовнішні посилання');
    });

    var $analogues = $('.inline-group').filter(function() {
        return $(this).find('h2').text().includes('АНАЛОГИ') || $(this).attr('id').indexOf('analogue') !== -1;
    });

    var $container = $form;

    // Переносимо елементи в потрібній послідовності (знизу вгору, щоб вставити правильно через prepend або insertAfter)
    if ($stocks.length) $container.append($stocks);
    if ($stickers.length) $container.append($stickers);
    if ($boxing.length) $container.append($boxing);
    if ($components.length) $container.append($components);
    if ($analogues.length) $container.append($analogues);
    if ($links.length) $container.append($links);
    if ($typeProps.length) $container.append($typeProps);
    if ($mainInfo.length) {
        $mainInfo.prependTo($container);
    }
    if ($photos.length) {
        $photos.prependTo($container); // Фото гарантовано стають на саме перше місце
    }
});